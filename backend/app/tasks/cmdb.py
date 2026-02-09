"""Celery tasks for asynchronous CMDB synchronization.

CMDB sync tasks are dispatched after key pipeline milestones (server
created, updated, decommissioned) so that ServiceNow stays in sync
without blocking the build pipeline.

All tasks are best-effort: failures are logged and retried a limited
number of times, but never propagated to the caller.  The pipeline
must never fail because ServiceNow is unreachable.
"""

import logging

from app.worker.celery_app import celery_app
from app.services.db import get_sync_db, get_server_request

logger = logging.getLogger(__name__)

# Event types that map to CMDBSyncService methods
_EVENT_DISPATCH = {
    "server_created": "sync_server_created",
    "server_updated": "sync_server_updated",
    "server_decommissioned": "sync_server_decommissioned",
}


@celery_app.task(
    name="tasks.cmdb_sync_server",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=120,
    ignore_result=False,
)
def cmdb_sync_server(
    self, server_request_id: str, event_type: str
) -> dict:
    """Sync a server event to ServiceNow CMDB asynchronously.

    Loads the server data from the database, then dispatches to the
    appropriate :class:`~app.services.cmdb_sync.CMDBSyncService`
    method based on ``event_type``.

    If the sync succeeds and produces a ``sys_id``, the server's
    ``cmdb_sys_id`` column is updated so that future syncs can
    reference the existing CI directly.

    Parameters
    ----------
    server_request_id:
        UUID string of the server request to sync.
    event_type:
        One of ``"server_created"``, ``"server_updated"``, or
        ``"server_decommissioned"``.

    Returns
    -------
    dict
        ``{"status": "synced"|"skipped"|"failed", ...}`` with details.
    """
    method_name = _EVENT_DISPATCH.get(event_type)
    if method_name is None:
        logger.error("Unknown CMDB event type: %r", event_type)
        return {
            "status": "error",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "detail": f"Unknown event type: {event_type}",
        }

    # Load server data from the database
    try:
        with get_sync_db() as session:
            server_data = get_server_request(session, server_request_id)
    except ValueError as exc:
        logger.error(
            "CMDB sync: ServerRequest not found: %s", server_request_id
        )
        return {
            "status": "failed",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "detail": str(exc),
        }

    # Read existing cmdb_sys_id from the model
    cmdb_sys_id = ""
    try:
        with get_sync_db() as session:
            from app.models.server import ServerRequest

            sr = session.get(ServerRequest, server_request_id)
            if sr is not None:
                cmdb_sys_id = sr.cmdb_sys_id or ""
                # Also add it to server_data for the sync service
                server_data["cmdb_sys_id"] = cmdb_sys_id
    except Exception:
        logger.debug(
            "Could not read cmdb_sys_id for %s (column may not exist yet)",
            server_request_id,
        )

    # Instantiate the sync service
    try:
        from app.services.cmdb_sync import CMDBSyncService

        sync_service = CMDBSyncService()
    except Exception as exc:
        logger.exception("Failed to create CMDBSyncService: %s", exc)
        return {
            "status": "failed",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "detail": f"Could not create CMDBSyncService: {exc}",
        }

    # Dispatch to the appropriate sync method
    try:
        method = getattr(sync_service, method_name)

        if event_type == "server_created":
            result = method(server_data)
        elif event_type in ("server_updated", "server_decommissioned"):
            result = method(server_data, cmdb_sys_id)
        else:
            result = None

        if result is None:
            logger.info(
                "CMDB sync returned None for %s (%s) -- "
                "integration may be disabled or call failed",
                server_request_id,
                event_type,
            )
            return {
                "status": "skipped",
                "event_type": event_type,
                "server_request_id": server_request_id,
            }

        # Persist the sys_id back to the server record
        new_sys_id = result.get("sys_id", "")
        if new_sys_id and new_sys_id != cmdb_sys_id:
            try:
                _update_cmdb_sys_id(server_request_id, new_sys_id)
            except Exception as exc:
                logger.warning(
                    "Failed to persist cmdb_sys_id for %s: %s",
                    server_request_id,
                    exc,
                )

        logger.info(
            "CMDB sync complete for %s: event=%s action=%s sys_id=%s",
            server_request_id,
            event_type,
            result.get("action", "unknown"),
            new_sys_id,
        )

        return {
            "status": "synced",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "action": result.get("action", "unknown"),
            "sys_id": new_sys_id,
        }

    except Exception as exc:
        logger.exception(
            "CMDB sync failed for %s (%s): %s",
            server_request_id,
            event_type,
            exc,
        )

        # Retry on transient errors
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.warning(
                "Max retries exceeded for CMDB sync: %s (%s)",
                server_request_id,
                event_type,
            )

        return {
            "status": "failed",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "detail": str(exc)[:500],
        }


@celery_app.task(
    name="tasks.cmdb_full_sync",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    soft_time_limit=600,
    ignore_result=False,
)
def cmdb_full_sync(self) -> dict:
    """Run a full CMDB reconciliation.

    Loads all server requests from the database and passes them to
    :meth:`~app.services.cmdb_sync.CMDBSyncService.full_sync` for
    reconciliation against ServiceNow.

    After the sync, any newly assigned ``sys_id`` values are persisted
    back to the ``cmdb_sys_id`` column on the corresponding server
    records.

    Returns
    -------
    dict
        Sync statistics with counts for created, updated, retired,
        failed, and skipped servers.
    """
    logger.info("Starting CMDB full sync")

    # Load all server requests
    try:
        with get_sync_db() as session:
            from app.models.server import ServerRequest as SR

            servers = session.query(SR).all()

            server_list = []
            for sr in servers:
                data = {
                    "id": str(sr.id),
                    "server_name": sr.server_name,
                    "environment": sr.environment,
                    "os_type": sr.os_type,
                    "instance_size": sr.instance_size,
                    "region": sr.region,
                    "status": sr.status,
                    "aws_instance_id": sr.aws_instance_id,
                    "private_ip": sr.private_ip,
                    "public_ip": sr.public_ip,
                    "dns_name": sr.dns_name,
                    "puppet_certname": sr.puppet_certname,
                    "cmdb_sys_id": sr.cmdb_sys_id or "",
                }
                server_list.append(data)

    except Exception as exc:
        logger.exception("Failed to load servers for CMDB full sync: %s", exc)
        return {
            "status": "failed",
            "detail": f"Database error: {exc}",
            "total": 0,
        }

    if not server_list:
        logger.info("No servers found for CMDB full sync")
        return {
            "status": "completed",
            "total": 0,
            "created": 0,
            "updated": 0,
            "retired": 0,
            "failed": 0,
            "skipped": 0,
        }

    # Run the sync
    try:
        from app.services.cmdb_sync import CMDBSyncService

        sync_service = CMDBSyncService()
        stats = sync_service.full_sync(server_list)
        stats["status"] = "completed"

        logger.info("CMDB full sync completed: %s", stats)
        return stats

    except Exception as exc:
        logger.exception("CMDB full sync failed: %s", exc)

        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.warning("Max retries exceeded for CMDB full sync")

        return {
            "status": "failed",
            "detail": str(exc)[:500],
            "total": len(server_list),
        }


def _update_cmdb_sys_id(server_request_id: str, sys_id: str) -> None:
    """Persist a CMDB sys_id to the server request record.

    Helper used after a successful CMDB sync to store the ServiceNow
    CI's ``sys_id`` so that subsequent syncs can reference the CI
    directly without a name-based lookup.
    """
    from datetime import datetime, timezone

    with get_sync_db() as session:
        from app.models.server import ServerRequest

        sr = session.get(ServerRequest, server_request_id)
        if sr is None:
            logger.warning(
                "Cannot persist cmdb_sys_id: ServerRequest %s not found",
                server_request_id,
            )
            return

        sr.cmdb_sys_id = sys_id
        sr.updated_at = datetime.now(timezone.utc)

    logger.info(
        "Persisted cmdb_sys_id=%s for ServerRequest %s",
        sys_id,
        server_request_id,
    )
