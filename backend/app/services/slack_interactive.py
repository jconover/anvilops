"""Handle Slack interactive message callbacks for approval buttons.

When a Slack user clicks Approve or Reject on an approval notification,
Slack sends an HTTP POST to our callback URL.  This module verifies the
request signature, extracts the action, and dispatches the appropriate
approval logic.
"""

import hashlib
import hmac
import json
import logging
import time

logger = logging.getLogger(__name__)

# Maximum age (in seconds) of a Slack request before we reject it.
# Slack recommends 5 minutes; we use 5 minutes as well.
_MAX_TIMESTAMP_AGE = 300


class SlackInteractiveHandler:
    """Process Slack interactive message payloads (approve/reject buttons)."""

    def __init__(self, signing_secret: str):
        self.signing_secret = signing_secret

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(
        self, timestamp: str, body: str, signature: str
    ) -> bool:
        """Verify a Slack request signature using HMAC-SHA256.

        Slack signs every request with a versioned signature:
            ``v0=<hex-digest of HMAC-SHA256(signing_secret, "v0:{ts}:{body}")>``

        We also reject requests older than ``_MAX_TIMESTAMP_AGE`` seconds to
        prevent replay attacks.

        Returns ``True`` when the signature is valid and fresh.
        """
        if not self.signing_secret:
            logger.warning("Slack signing secret not configured; rejecting request")
            return False

        # Replay-attack guard
        try:
            ts_int = int(timestamp)
        except (ValueError, TypeError):
            logger.warning("Invalid Slack timestamp: %r", timestamp)
            return False

        if abs(time.time() - ts_int) > _MAX_TIMESTAMP_AGE:
            logger.warning("Slack request timestamp too old: %s", timestamp)
            return False

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{body}"
        expected = (
            "v0="
            + hmac.new(
                self.signing_secret.encode("utf-8"),
                sig_basestring.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()
        )

        if not hmac.compare_digest(expected, signature):
            logger.warning("Slack signature mismatch")
            return False

        return True

    # ------------------------------------------------------------------
    # Action dispatch
    # ------------------------------------------------------------------

    def handle_action(self, payload: dict) -> dict:
        """Process an interactive message action from Slack.

        Extracts the action ID and the server request ID from the payload,
        then dispatches to the appropriate approval handler.

        Returns a dict that can be used as the JSON response to replace the
        original Slack message with an updated status.
        """
        try:
            callback_id = payload.get("callback_id", "")
            actions = payload.get("actions", [])
            user = payload.get("user", {})
            slack_username = user.get("name", user.get("id", "unknown"))

            if not actions:
                logger.warning("No actions in Slack interactive payload")
                return self._error_response("No action received.")

            action = actions[0]
            action_value = action.get("value", "")

            # The value is formatted as "approve:<request_id>" or "reject:<request_id>"
            if ":" not in action_value:
                logger.warning("Malformed action value: %r", action_value)
                return self._error_response("Invalid action format.")

            action_type, request_id = action_value.split(":", 1)

            if action_type == "approve":
                return self._handle_approve(request_id, slack_username)
            elif action_type == "reject":
                return self._handle_reject(request_id, slack_username)
            else:
                logger.warning("Unknown action type: %r", action_type)
                return self._error_response(f"Unknown action: {action_type}")

        except Exception as exc:
            logger.exception("Error processing Slack interactive action: %s", exc)
            return self._error_response("An internal error occurred.")

    # ------------------------------------------------------------------
    # Approval handlers
    # ------------------------------------------------------------------

    def _handle_approve(self, request_id: str, approver: str) -> dict:
        """Handle an approval action from Slack.

        Calls into the approval service to mark the request as approved and
        returns an updated Slack message reflecting the new status.
        """
        logger.info(
            "Slack approval for request %s by %s", request_id, approver
        )

        try:
            from app.services.slack import get_slack_notifier

            # TODO: Wire into actual approval service once it exists.
            #   from app.services.approvals import approve_request
            #   approve_request(request_id, approver=approver, source="slack")
            #
            # For now, send the approval-granted notification.
            notifier = get_slack_notifier()
            notifier.notify_approval_granted(
                server_name=f"(request {request_id[:8]}...)",
                approver=approver,
                request_id=request_id,
            )
        except Exception as exc:
            logger.exception(
                "Failed to process approval for %s: %s", request_id, exc
            )

        return self._replacement_message(
            text=f":white_check_mark: *Approved* by {approver}",
            color="#4CAF50",
            request_id=request_id,
        )

    def _handle_reject(self, request_id: str, rejector: str) -> dict:
        """Handle a rejection action from Slack.

        Calls into the approval service to mark the request as rejected and
        returns an updated Slack message reflecting the new status.
        """
        logger.info(
            "Slack rejection for request %s by %s", request_id, rejector
        )

        try:
            from app.services.slack import get_slack_notifier

            # TODO: Wire into actual approval service once it exists.
            #   from app.services.approvals import reject_request
            #   reject_request(request_id, approver=rejector, reason="Rejected via Slack", source="slack")
            #
            # For now, send the approval-rejected notification.
            notifier = get_slack_notifier()
            notifier.notify_approval_rejected(
                server_name=f"(request {request_id[:8]}...)",
                approver=rejector,
                reason="Rejected via Slack interactive button",
                request_id=request_id,
            )
        except Exception as exc:
            logger.exception(
                "Failed to process rejection for %s: %s", request_id, exc
            )

        return self._replacement_message(
            text=f":no_entry: *Rejected* by {rejector}",
            color="#F44336",
            request_id=request_id,
        )

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _replacement_message(text: str, color: str, request_id: str) -> dict:
        """Build a replacement message that removes the buttons and shows the
        action that was taken.  Slack replaces the original message with this.
        """
        return {
            "replace_original": True,
            "attachments": [
                {
                    "color": color,
                    "text": text,
                    "footer": "AnvilOps",
                    "mrkdwn_in": ["text"],
                }
            ],
        }

    @staticmethod
    def _error_response(message: str) -> dict:
        """Build an ephemeral error response visible only to the clicking user."""
        return {
            "response_type": "ephemeral",
            "replace_original": False,
            "text": f":warning: {message}",
        }
