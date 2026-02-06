"""Server API endpoints."""

import secrets
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.server import ServerRequest
from app.schemas.server import (
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
    request: ServerCreateRequest,
    db: AsyncSession = Depends(get_db),
):
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
    status: str | None = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
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
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific server request."""
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    return server


@router.delete("/{server_id}", response_model=ServerResponse)
async def decommission_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Request server decommission."""
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

    server.status = "decommissioning"
    await db.flush()
    await db.refresh(server)

    logger.info("Server %s marked for decommission", server.server_name)
    return server
