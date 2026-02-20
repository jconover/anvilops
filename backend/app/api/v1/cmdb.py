"""CMDB integration API endpoints.

Provides endpoints to check CMDB sync status, trigger manual syncs,
and view synchronization statistics.

All endpoints require authentication (to be enforced once Cognito RBAC
is wired up).  In the future, only Admins will be permitted to trigger
full reconciliation syncs.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.server import ServerRequest
from app.schemas.cmdb import (
    CMDBFullSyncResponse,
    CMDBSyncStatsResponse,
    CMDBSyncStatusResponse,
    CMDBSyncTriggerResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status/{server_id}", response_model=CMDBSyncStatusResponse)
async def get_cmdb_status(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get CMDB sync status for a server.

    Returns the server's CMDB ``sys_id`` and, if the ServiceNow
    integration is enabled, fetches the current CI record and its
    relationships from ServiceNow.
    """
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    cmdb_sys_id = server.cmdb_sys_id
    cmdb_ci = None
    relationships = []

    # If there is a CMDB sys_id, try to fetch the CI from ServiceNow
    if cmdb_sys_id:
        try:
            from app.services.servicenow import get_servicenow_client

            client = get_servicenow_client()
            cmdb_ci = client.get_ci(cmdb_sys_id)
            if cmdb_ci:
                relationships = client.get_ci_relationships(cmdb_sys_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch CMDB CI for %s (sys_id=%s): %s",
                server.server_name,
                cmdb_sys_id,
                exc,
            )

    return CMDBSyncStatusResponse(
        server_id=server.id,
        server_name=server.server_name,
        cmdb_sys_id=cmdb_sys_id,
        cmdb_synced=bool(cmdb_sys_id),
        cmdb_ci=cmdb_ci,
        relationships=relationships,
    )


@router.post("/sync/{server_id}", response_model=CMDBSyncTriggerResponse)
async def trigger_cmdb_sync(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger manual CMDB sync for a server.

    Dispatches a Celery task to sync the server's data with ServiceNow.
    The sync runs asynchronously; use ``GET /cmdb/status/{server_id}``
    to check the result.

    The event type is determined automatically based on the server's
    current status:
    - ``decommissioned`` -> ``server_decommissioned``
    - servers with a ``cmdb_sys_id`` -> ``server_updated``
    - servers without a ``cmdb_sys_id`` -> ``server_created``
    """
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    # Determine the appropriate event type
    if server.status == "decommissioned":
        event_type = "server_decommissioned"
    elif server.cmdb_sys_id:
        event_type = "server_updated"
    else:
        event_type = "server_created"

    # Dispatch the Celery task
    try:
        from app.tasks.cmdb import cmdb_sync_server

        task = cmdb_sync_server.delay(str(server.id), event_type)
        task_id = task.id
    except Exception as exc:
        logger.error(
            "Failed to dispatch CMDB sync task for %s: %s",
            server.server_name,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispatch CMDB sync task: {exc}",
        )

    logger.info(
        "Triggered CMDB sync for %s (%s): event=%s task=%s",
        server.server_name,
        server.id,
        event_type,
        task_id,
    )

    return CMDBSyncTriggerResponse(
        server_id=server.id,
        server_name=server.server_name,
        task_id=task_id,
        message=f"CMDB sync triggered ({event_type})",
    )


@router.post("/sync", response_model=CMDBFullSyncResponse)
async def trigger_full_cmdb_sync():
    """Trigger full CMDB reconciliation.

    Dispatches a Celery task that loads all servers and reconciles
    them against ServiceNow CMDB.  This is a long-running operation;
    use ``GET /cmdb/stats`` to monitor progress.

    In the future, this endpoint will be restricted to Admin role.
    """
    try:
        from app.tasks.cmdb import cmdb_full_sync

        task = cmdb_full_sync.delay()
        task_id = task.id
    except Exception as exc:
        logger.error("Failed to dispatch CMDB full sync task: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispatch CMDB full sync task: {exc}",
        )

    logger.info("Triggered CMDB full sync: task=%s", task_id)

    return CMDBFullSyncResponse(
        task_id=task_id,
        message="Full CMDB reconciliation triggered",
    )


@router.get("/stats", response_model=CMDBSyncStatsResponse)
async def get_cmdb_stats(
    db: AsyncSession = Depends(get_db),
):
    """CMDB sync statistics.

    Returns counts of synced vs. unsynced servers, grouped by status,
    along with the ServiceNow integration configuration status.
    """
    # Total server count
    total_result = await db.execute(
        select(func.count()).select_from(ServerRequest)
    )
    total = total_result.scalar() or 0

    # Synced count (servers with a cmdb_sys_id)
    synced_result = await db.execute(
        select(func.count())
        .select_from(ServerRequest)
        .where(ServerRequest.cmdb_sys_id.is_not(None))
        .where(ServerRequest.cmdb_sys_id != "")
    )
    synced = synced_result.scalar() or 0

    # Counts by status
    status_query = (
        select(
            ServerRequest.status,
            func.count().label("cnt"),
        )
        .group_by(ServerRequest.status)
    )
    status_result = await db.execute(status_query)
    by_status = {row.status: row.cnt for row in status_result.all()}

    # ServiceNow configuration
    from app.core.config import settings

    instance_url = settings.SERVICENOW_INSTANCE_URL
    # Mask the instance URL for display (show domain only)
    if instance_url:
        masked = instance_url.replace("https://", "").replace("http://", "")
        masked = masked.split("/")[0]  # Just the hostname
    else:
        masked = "(not configured)"

    return CMDBSyncStatsResponse(
        total_servers=total,
        synced=synced,
        unsynced=total - synced,
        by_status=by_status,
        servicenow_enabled=settings.SERVICENOW_ENABLED,
        servicenow_instance=masked,
    )
