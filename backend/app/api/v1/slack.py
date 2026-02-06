"""Slack interactive message webhook receiver.

Slack sends an HTTP POST to ``/api/v1/slack/interactions`` whenever a user
clicks an interactive button (e.g. Approve / Reject on an approval
notification).  This endpoint:

1. Verifies the Slack request signature (HMAC-SHA256).
2. Parses the ``payload`` form field as JSON.
3. Dispatches to :class:`SlackInteractiveHandler` for processing.
4. Returns the replacement message so Slack updates the original.
"""

import json
import logging

from fastapi import APIRouter, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.services.slack_interactive import SlackInteractiveHandler

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/interactions")
async def slack_interactions(
    request: Request,
    payload: str = Form(...),
    x_slack_request_timestamp: str = Header("", alias="X-Slack-Request-Timestamp"),
    x_slack_signature: str = Header("", alias="X-Slack-Signature"),
):
    """Receive and process Slack interactive message callbacks.

    Slack sends the payload as a URL-encoded form field named ``payload``
    containing a JSON string.  The request includes HMAC-SHA256 headers
    for verification.
    """
    handler = SlackInteractiveHandler(signing_secret=settings.SLACK_SIGNING_SECRET)

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------
    # We need the raw request body for signature verification because Slack
    # signs the raw bytes, not the parsed form fields.
    raw_body = await request.body()
    body_str = raw_body.decode("utf-8")

    if settings.SLACK_SIGNING_SECRET:
        if not handler.verify_signature(
            timestamp=x_slack_request_timestamp,
            body=body_str,
            signature=x_slack_signature,
        ):
            logger.warning("Slack signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")
    else:
        logger.warning(
            "SLACK_SIGNING_SECRET not configured; skipping signature verification"
        )

    # ------------------------------------------------------------------
    # Parse and dispatch
    # ------------------------------------------------------------------
    try:
        payload_data = json.loads(payload)
    except json.JSONDecodeError:
        logger.error("Failed to parse Slack interaction payload")
        raise HTTPException(status_code=400, detail="Invalid payload")

    logger.info(
        "Received Slack interaction: callback_id=%s, user=%s",
        payload_data.get("callback_id", ""),
        payload_data.get("user", {}).get("name", "unknown"),
    )

    result = handler.handle_action(payload_data)
    return JSONResponse(content=result)
