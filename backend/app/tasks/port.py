"""Celery tasks for asynchronous Port IDP catalog synchronization.

Port sync tasks are dispatched after key pipeline milestones (server
created, updated, decommissioned) so that the Port software catalog
stays in sync without blocking the build pipeline.

All tasks are best-effort: failures are logged and retried a limited
number of times, but never propagated to the caller.  The pipeline
must never fail because Port is unreachable.
"""

import logging
import re

from app.services.db import get_server_request, get_sync_db
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

# Blueprint identifier used for all AnvilOps server entities in Port
_BLUEPRINT_ID = "anvilops_server"


def _slugify(value: str) -> str:
    """Convert a server name to a Port-safe entity identifier.

    Lowercases the string and replaces any run of non-alphanumeric
    characters with a single hyphen, then strips leading/trailing hyphens.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or value.lower()


def _build_entity_payload(server_data: dict) -> dict:
    """Map server_data fields to the Port entity structure.

    Returns a dict with keys: blueprint_id, entity_id, title,
    properties, relations.
    """
    server_name = server_data.get("server_name") or ""
    entity_id = _slugify(server_name)

    properties = {
        "server_name": server_name,
        "environment": server_data.get("environment"),
        "os_type": server_data.get("os_type"),
        "instance_size": server_data.get("instance_size"),
        "region": server_data.get("region"),
        "status": server_data.get("status"),
        "private_ip": server_data.get("private_ip"),
        "public_ip": server_data.get("public_ip"),
        "dns_name": server_data.get("dns_name"),
        "aws_instance_id": server_data.get("aws_instance_id"),
        "puppet_certname": server_data.get("puppet_certname"),
    }
    # Drop None values so Port doesn't overwrite existing props with null
    properties = {k: v for k, v in properties.items() if v is not None}

    relations: dict = {}
    template_id = server_data.get("template_id")
    if template_id:
        relations["server_template"] = template_id

    return {
        "blueprint_id": _BLUEPRINT_ID,
        "entity_id": entity_id,
        "title": server_name,
        "properties": properties,
        "relations": relations or None,
    }


@celery_app.task(
    name="tasks.port_sync_server",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    soft_time_limit=120,
    ignore_result=False,
)
def port_sync_server(self, server_request_id: str, event_type: str) -> dict:
    """Sync a server lifecycle event to the Port IDP catalog.

    Loads the server data from the database, maps it to a Port entity,
    then upserts or deletes the entity depending on ``event_type``.

    If the upsert succeeds and produces an entity identifier, the
    server's ``port_entity_id`` column is updated so that future syncs
    can reference the existing entity directly.

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
    if event_type not in ("server_created", "server_updated", "server_decommissioned"):
        logger.error("Unknown Port event type: %r", event_type)
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
            "Port sync: ServerRequest not found: %s", server_request_id
        )
        return {
            "status": "failed",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "detail": str(exc),
        }

    # Read existing port_entity_id from the model (column may not exist yet)
    port_entity_id = ""
    try:
        with get_sync_db() as session:
            from app.models.server import ServerRequest

            sr = session.get(ServerRequest, server_request_id)
            if sr is not None:
                port_entity_id = getattr(sr, "port_entity_id", None) or ""
                server_data["port_entity_id"] = port_entity_id
                # Also expose template_id for relation mapping
                server_data.setdefault(
                    "template_id", getattr(sr, "template_id", None)
                )
    except Exception:
        logger.debug(
            "Could not read port_entity_id for %s (column may not exist yet)",
            server_request_id,
        )

    # Create the sync service
    try:
        from app.services.port import get_port_service_sync

        port_service = get_port_service_sync()
    except Exception as exc:
        logger.exception("Failed to create PortServiceSync: %s", exc)
        return {
            "status": "failed",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "detail": f"Could not create PortServiceSync: {exc}",
        }

    # Dispatch to the appropriate Port API call
    try:
        if event_type == "server_decommissioned":
            # Determine which entity identifier to delete
            entity_id_to_delete = port_entity_id or _slugify(
                server_data.get("server_name") or server_request_id
            )
            deleted = port_service.delete_entity(_BLUEPRINT_ID, entity_id_to_delete)
            if not deleted:
                logger.info(
                    "Port delete returned False for %s (%s) -- "
                    "integration may be disabled or entity absent",
                    server_request_id,
                    event_type,
                )
                return {
                    "status": "skipped",
                    "event_type": event_type,
                    "server_request_id": server_request_id,
                }

            logger.info(
                "Port sync complete for %s: event=%s entity_id=%s deleted",
                server_request_id,
                event_type,
                entity_id_to_delete,
            )
            return {
                "status": "synced",
                "event_type": event_type,
                "server_request_id": server_request_id,
                "action": "deleted",
                "entity_id": entity_id_to_delete,
            }

        # server_created or server_updated — both use upsert
        payload = _build_entity_payload(server_data)
        result = port_service.upsert_entity(
            blueprint_id=payload["blueprint_id"],
            entity_id=payload["entity_id"],
            title=payload["title"],
            properties=payload["properties"],
            relations=payload["relations"],
        )

        if result is None:
            logger.info(
                "Port upsert returned None for %s (%s) -- "
                "integration may be disabled or call failed",
                server_request_id,
                event_type,
            )
            return {
                "status": "skipped",
                "event_type": event_type,
                "server_request_id": server_request_id,
            }

        # Persist the entity identifier back to the server record
        new_entity_id = result.get("identifier", "") or payload["entity_id"]
        if new_entity_id and new_entity_id != port_entity_id:
            try:
                _update_port_entity_id(server_request_id, new_entity_id)
            except Exception as exc:
                logger.warning(
                    "Failed to persist port_entity_id for %s: %s",
                    server_request_id,
                    exc,
                )

        logger.info(
            "Port sync complete for %s: event=%s action=upserted entity_id=%s",
            server_request_id,
            event_type,
            new_entity_id,
        )

        return {
            "status": "synced",
            "event_type": event_type,
            "server_request_id": server_request_id,
            "action": "upserted",
            "entity_id": new_entity_id,
        }

    except Exception as exc:
        logger.exception(
            "Port sync failed for %s (%s): %s",
            server_request_id,
            event_type,
            exc,
        )

        # Retry on transient errors
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.warning(
                "Max retries exceeded for Port sync: %s (%s)",
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
    name="tasks.port_full_sync",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
    soft_time_limit=600,
    ignore_result=False,
)
def port_full_sync(self) -> dict:
    """Run a full Port catalog reconciliation.

    Loads all server requests from the database and upserts each one
    to the Port software catalog.  Any newly assigned entity identifiers
    are persisted back to the ``port_entity_id`` column on the
    corresponding server records.

    Returns
    -------
    dict
        Sync statistics with counts for synced, skipped, and failed servers.
    """
    logger.info("Starting Port full sync")

    # Load all server requests
    try:
        with get_sync_db() as session:
            from app.models.server import ServerRequest

            servers = session.query(ServerRequest).all()

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
                    "puppet_certname": getattr(sr, "puppet_certname", None),
                    "template_id": getattr(sr, "template_id", None),
                    "port_entity_id": getattr(sr, "port_entity_id", None) or "",
                }
                server_list.append(data)

    except Exception as exc:
        logger.exception("Failed to load servers for Port full sync: %s", exc)
        return {
            "status": "failed",
            "detail": f"Database error: {exc}",
            "total": 0,
        }

    if not server_list:
        logger.info("No servers found for Port full sync")
        return {
            "status": "completed",
            "total": 0,
            "synced": 0,
            "skipped": 0,
            "failed": 0,
        }

    # Create the sync service once for all upserts
    try:
        from app.services.port import get_port_service_sync

        port_service = get_port_service_sync()
    except Exception as exc:
        logger.exception("Failed to create PortServiceSync for full sync: %s", exc)

        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.warning("Max retries exceeded for Port full sync")

        return {
            "status": "failed",
            "detail": f"Could not create PortServiceSync: {exc}",
            "total": len(server_list),
        }

    stats = {"synced": 0, "skipped": 0, "failed": 0}

    for server_data in server_list:
        server_request_id = server_data["id"]
        existing_entity_id = server_data.get("port_entity_id", "")
        try:
            payload = _build_entity_payload(server_data)
            result = port_service.upsert_entity(
                blueprint_id=payload["blueprint_id"],
                entity_id=payload["entity_id"],
                title=payload["title"],
                properties=payload["properties"],
                relations=payload["relations"],
            )

            if result is None:
                stats["skipped"] += 1
                continue

            new_entity_id = result.get("identifier", "") or payload["entity_id"]
            if new_entity_id and new_entity_id != existing_entity_id:
                try:
                    _update_port_entity_id(server_request_id, new_entity_id)
                except Exception as persist_exc:
                    logger.warning(
                        "Failed to persist port_entity_id for %s: %s",
                        server_request_id,
                        persist_exc,
                    )

            stats["synced"] += 1

        except Exception as exc:
            logger.exception(
                "Port full sync: upsert failed for %s: %s",
                server_request_id,
                exc,
            )
            stats["failed"] += 1

    stats["status"] = "completed"
    stats["total"] = len(server_list)
    logger.info("Port full sync completed: %s", stats)
    return stats


def _update_port_entity_id(server_request_id: str, entity_id: str) -> None:
    """Persist a Port entity identifier to the server request record.

    Helper used after a successful Port upsert to store the entity's
    identifier so that subsequent syncs can reference it directly.
    """
    from datetime import datetime, timezone

    with get_sync_db() as session:
        from app.models.server import ServerRequest

        sr = session.get(ServerRequest, server_request_id)
        if sr is None:
            logger.warning(
                "Cannot persist port_entity_id: ServerRequest %s not found",
                server_request_id,
            )
            return

        if not hasattr(sr, "port_entity_id"):
            logger.debug(
                "port_entity_id column not present on ServerRequest %s -- skipping",
                server_request_id,
            )
            return

        sr.port_entity_id = entity_id
        sr.updated_at = datetime.now(timezone.utc)

    logger.info(
        "Persisted port_entity_id=%s for ServerRequest %s",
        entity_id,
        server_request_id,
    )
