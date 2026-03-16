"""Server API endpoints."""

import logging
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.db.session import get_db
from app.models.server import ServerRequest
from app.models.server import BuildStep
from app.schemas.server import (
    BuildStepResponse,
    ServerCreateRequest,
    ServerListResponse,
    ServerResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ENV_ABBREV = {"dev": "DEV", "staging": "STG", "production": "PROD"}
ROLE_ABBREV = {
    "base": "SRV",
    "web_server": "WEB",
    "db_server": "DB",
    "app_server": "APP",
    "dev_workstation": "DEV",
}


def generate_server_name(environment: str, puppet_role: str) -> str:
    """Generate server name in ENV-ROLE-RANDOM format (e.g. PROD-WEB-a3f8)."""
    env = ENV_ABBREV.get(environment, "SRV")
    role = ROLE_ABBREV.get(puppet_role, "SRV")
    suffix = secrets.token_hex(2)
    return f"{env}-{role}-{suffix}"


@router.post("/", response_model=ServerResponse, status_code=202)
async def create_server(
    user: CurrentUser,
    request: ServerCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ServerResponse:
    """Create a new server build request."""
    server_name = request.server_name or generate_server_name(
        request.environment, request.puppet_role
    )

    server = ServerRequest(
        id=uuid.uuid4(),
        server_name=server_name,
        environment=request.environment,
        os_type=request.os_type,
        instance_size=request.instance_size,
        region=request.region,
        vpc_id=request.vpc_id,
        subnet_id=request.subnet_id,
        security_profile=request.security_profile,
        domain_join=request.domain_join,
        software_packages=request.software_packages,
        puppet_role=request.puppet_role,
        additional_storage=[s.model_dump() for s in request.additional_storage],
        tags=request.tags,
        template_id=request.template_id,
        status="pending",
    )

    db.add(server)
    await db.flush()
    await db.refresh(server)

    # Dispatch Celery build task
    try:
        from app.tasks.orchestrator import run_server_build
        run_server_build.delay(str(server.id))
    except ImportError:
        logger.warning("Celery tasks not yet available, skipping dispatch")

    logger.info("Created server request: %s (%s)", server.server_name, server.id)
    return server


@router.get("/", response_model=ServerListResponse)
async def list_servers(
    user: CurrentUser,
    status: str | None = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ServerListResponse:
    """List all server requests with optional filtering."""
    query = select(ServerRequest)
    count_query = select(func.count(ServerRequest.id))

    if status:
        query = query.where(ServerRequest.status == status)
        count_query = count_query.where(ServerRequest.status == status)

    query = query.order_by(ServerRequest.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    servers = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return ServerListResponse(servers=servers, total=total)


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ServerResponse:
    """Get a specific server request."""
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    return server


@router.get("/{server_id}/steps", response_model=list[BuildStepResponse])
async def get_server_build_steps(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[BuildStepResponse]:
    """Get the build pipeline steps for a server request."""
    result = await db.execute(
        select(BuildStep)
        .where(BuildStep.server_request_id == server_id)
        .order_by(BuildStep.step_order)
    )
    steps = result.scalars().all()
    return steps


@router.post("/{server_id}/cancel", response_model=ServerResponse)
async def cancel_server(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ServerResponse:
    """Cancel a pending server request.

    Only requests in ``pending`` status can be cancelled -- no
    infrastructure has been provisioned yet so this is a safe,
    lightweight operation that simply marks the request as cancelled
    and attempts to revoke the queued Celery build task.
    """
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    if server.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Server request is already cancelled",
        )

    if server.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Server request cannot be cancelled from status '{server.status}'. "
                "Only requests in 'pending' status can be cancelled."
            ),
        )

    server.status = "cancelled"
    server.status_message = "Cancelled by user"
    await db.flush()
    await db.refresh(server)

    # Attempt to revoke the Celery build task (best-effort)
    try:
        from app.worker.celery_app import celery_app as _celery
        _celery.control.revoke(f"build-{server_id}", terminate=False)
    except Exception:
        logger.debug("Could not revoke Celery task for %s (may not be queued yet)", server_id)

    logger.info("Cancelled server request %s (%s)", server.server_name, server.id)
    return server


@router.post("/{server_id}/decommission", response_model=ServerResponse)
async def decommission_server(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ServerResponse:
    """Trigger server decommission workflow.

    Validates the server is in a decommissionable state (``ready`` or
    ``failed``), marks it as ``decommissioning``, and dispatches the
    Celery decommission task that runs the full reverse pipeline:
    Puppet purge -> AWX decommission -> Terraform destroy -> DNS cleanup.

    Returns the updated server with status ``decommissioning``.
    """
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    if server.status in ("decommissioning", "decommissioned"):
        raise HTTPException(
            status_code=400,
            detail=f"Server is already {server.status}",
        )

    if server.status not in ("ready", "failed"):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Server cannot be decommissioned from status '{server.status}'. "
                "Only servers in 'ready' or 'failed' status can be decommissioned."
            ),
        )

    server.status = "decommissioning"
    server.status_message = "Decommission requested"
    await db.flush()
    await db.refresh(server)

    # Dispatch Celery decommission task
    try:
        from app.tasks.decommission import run_server_decommission
        run_server_decommission.delay(str(server.id))
    except ImportError:
        logger.warning("Celery decommission task not yet available, skipping dispatch")

    logger.info("Server %s (%s) marked for decommission", server.server_name, server.id)
    return server


@router.delete("/{server_id}", response_model=ServerResponse)
async def delete_server(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ServerResponse:
    """Delete a decommissioned server request record.

    Only servers in ``decommissioned`` status can be deleted.  For active
    servers, use the ``POST /{server_id}/decommission`` endpoint to
    trigger the full teardown workflow first.
    """
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    if server.status != "decommissioned":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Only decommissioned servers can be deleted. "
                f"Current status: '{server.status}'. "
                "Use POST /{server_id}/decommission to tear down first."
            ),
        )

    await db.delete(server)
    await db.flush()

    logger.info("Deleted decommissioned server record %s (%s)", server.server_name, server.id)
    return server
