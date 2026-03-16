"""Port IDP webhook receiver and sync endpoints.

Port sends HTTP POST callbacks to ``/api/v1/port/webhook`` when users trigger
self-service actions in the Port portal.  This module:

1. Verifies the Port webhook HMAC-SHA256 signature.
2. Parses the payload as a ``PortWebhookPayload``.
3. Dispatches to the appropriate Celery task based on the action name.

Additional endpoints support health checks and manual catalog sync triggers.
"""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from app.core.auth import CurrentUser

from app.core.config import settings
from app.schemas.port import PortWebhookPayload
from app.services.port import get_port_service, verify_webhook_signature
from app.tasks.port import port_full_sync, port_sync_server

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def port_webhook(
    request: Request,
    x_port_signature: str = Header("", alias="x-port-signature"),
) -> dict:
    """Receive and process Port self-service action callbacks.

    Port signs the raw request body with HMAC-SHA256.  The signature is
    delivered in the ``x-port-signature`` header as ``sha256=<hex-digest>``.
    """
    # ------------------------------------------------------------------
    # Read raw body for signature verification
    # ------------------------------------------------------------------
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------
    if settings.PORT_WEBHOOK_SECRET:
        if not verify_webhook_signature(body_str, x_port_signature):
            logger.warning("Port webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning(
            "PORT_WEBHOOK_SECRET not configured; skipping signature verification"
        )

    # ------------------------------------------------------------------
    # Parse payload
    # ------------------------------------------------------------------
    try:
        raw_data = json.loads(body_str)
        payload = PortWebhookPayload(**raw_data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse Port webhook payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(
        "Received Port self-service action: action=%s blueprint=%s triggered_by=%s",
        payload.action,
        payload.blueprint,
        payload.triggered_by or "unknown",
    )

    # ------------------------------------------------------------------
    # Dispatch based on action
    # ------------------------------------------------------------------
    if payload.action == "provision_server":
        # TODO: queue server build task once server provisioning task is wired
        # e.g. build_server.delay(payload.properties)
        logger.info(
            "Port action 'provision_server' received; queuing not yet implemented"
        )
        return {"ok": True, "action": payload.action}

    if payload.action == "decommission_server":
        # TODO: queue decommission task once decommission task is wired
        # e.g. decommission_server.delay(payload.entity_identifier)
        logger.info(
            "Port action 'decommission_server' received; queuing not yet implemented"
        )
        return {"ok": True, "action": payload.action}

    if payload.action == "scale_group":
        # TODO: queue scaling action task once scaling task is wired
        # e.g. scale_group.delay(payload.entity_identifier, payload.properties)
        logger.info(
            "Port action 'scale_group' received; queuing not yet implemented"
        )
        return {"ok": True, "action": payload.action}

    logger.warning("Unknown Port action received: %s", payload.action)
    raise HTTPException(
        status_code=422,
        detail=f"Unknown action: {payload.action!r}",
    )


@router.get("/health")
async def port_health(user: CurrentUser) -> dict:
    """Check Port integration health.

    Instantiates a PortService and calls ``health_check()`` to verify that
    the Port API is reachable and the configured credentials are valid.
    """
    service = get_port_service()
    try:
        healthy = await service.health_check()
    finally:
        await service.close()

    return {"healthy": healthy, "integration": "port"}


@router.post("/sync/{server_request_id}")
async def port_sync_server_endpoint(
    user: CurrentUser,
    server_request_id: str,
    event_type: str = Query(default="server_updated"),
) -> dict:
    """Manually trigger a Port catalog sync for a single server.

    Enqueues a ``port_sync_server`` Celery task for the given
    ``server_request_id`` and returns the task ID.
    """
    result = port_sync_server.delay(server_request_id, event_type)
    logger.info(
        "Queued port_sync_server task: server_request_id=%s event_type=%s task_id=%s",
        server_request_id,
        event_type,
        result.id,
    )
    return {"queued": True, "task_id": result.id}


@router.post("/sync")
async def port_full_sync_endpoint(user: CurrentUser) -> dict:
    """Manually trigger a full Port catalog sync.

    Enqueues a ``port_full_sync`` Celery task that syncs all AnvilOps
    entities to the Port catalog.
    """
    result = port_full_sync.delay()
    logger.info("Queued port_full_sync task: task_id=%s", result.id)
    return {"queued": True, "task_id": result.id}
