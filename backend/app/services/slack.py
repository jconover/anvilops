"""Slack webhook notification service for AnvilOps.

Sends formatted messages to Slack channels for key pipeline events:
  - Build started
  - Build completed (success)
  - Build failed
  - Approval requested
  - Approval granted/rejected
  - Decommission started/completed

All notifications are best-effort: failures are logged but never raise
exceptions that could affect the build pipeline.
"""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# Sidebar colors for different notification types
COLOR_INFO = "#2196F3"       # Blue
COLOR_SUCCESS = "#4CAF50"    # Green
COLOR_FAILURE = "#F44336"    # Red
COLOR_WARNING = "#FFC107"    # Yellow/Amber
COLOR_DECOM = "#FF9800"      # Orange
COLOR_NEUTRAL = "#9E9E9E"    # Gray


class SlackNotifier:
    """Send notifications to Slack via incoming webhooks.

    All public methods return ``True`` on success and ``False`` on failure.
    They never raise exceptions so that calling code can fire-and-forget.
    """

    def __init__(
        self,
        webhook_url: str,
        enabled: bool = True,
        app_url: str = "http://localhost:3000",
        channel: str | None = None,
        timeout: float = 10.0,
    ):
        self.webhook_url = webhook_url
        self.enabled = enabled
        self.app_url = app_url.rstrip("/")
        self.channel = channel
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Core transport
    # ------------------------------------------------------------------

    def send_message(self, payload: dict) -> bool:
        """Send a message payload to the Slack webhook.

        Returns ``True`` on success, ``False`` on any failure.  Errors are
        logged but never propagated so that notifications remain best-effort.
        """
        if not self.enabled:
            logger.info("Slack notifications disabled, skipping")
            return False

        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured, skipping")
            return False

        # Optionally override the channel if configured
        if self.channel:
            payload.setdefault("channel", self.channel)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.webhook_url, json=payload)

            if response.status_code != 200:
                logger.error(
                    "Slack webhook returned HTTP %s: %s",
                    response.status_code,
                    response.text[:500],
                )
                return False

            logger.debug("Slack notification sent successfully")
            return True

        except httpx.TimeoutException:
            logger.warning("Slack webhook timed out after %.1fs", self.timeout)
            return False
        except httpx.HTTPError as exc:
            logger.warning("Slack webhook HTTP error: %s", exc)
            return False
        except Exception as exc:
            logger.exception("Unexpected error sending Slack notification: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Build lifecycle notifications
    # ------------------------------------------------------------------

    def notify_build_started(
        self,
        server_name: str,
        environment: str,
        os_type: str,
        instance_size: str,
        request_id: str,
    ) -> bool:
        """Send a build-started notification with server details."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
            {"title": "Environment", "value": environment.upper(), "short": True},
            {"title": "OS", "value": os_type, "short": True},
            {"title": "Instance Size", "value": instance_size, "short": True},
        ]

        attachment = self._build_attachment(
            color=COLOR_INFO,
            title=":rocket: Build Started",
            text=f"Server *{server_name}* is being provisioned.",
            fields=fields,
            request_id=request_id,
        )

        return self.send_message({"attachments": [attachment]})

    def notify_build_completed(
        self,
        server_name: str,
        environment: str,
        private_ip: str | None,
        dns_name: str | None,
        request_id: str,
        duration_seconds: int | None = None,
    ) -> bool:
        """Send a build-success notification."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
            {"title": "Environment", "value": environment.upper(), "short": True},
        ]

        if private_ip:
            fields.append({"title": "Private IP", "value": private_ip, "short": True})
        if dns_name:
            fields.append({"title": "DNS", "value": dns_name, "short": True})
        if duration_seconds is not None:
            fields.append(
                {
                    "title": "Duration",
                    "value": self._format_duration(duration_seconds),
                    "short": True,
                }
            )

        attachment = self._build_attachment(
            color=COLOR_SUCCESS,
            title=":white_check_mark: Build Completed",
            text=f"Server *{server_name}* is ready.",
            fields=fields,
            request_id=request_id,
        )

        return self.send_message({"attachments": [attachment]})

    def notify_build_failed(
        self,
        server_name: str,
        environment: str,
        error: str,
        request_id: str,
        step: str | None = None,
    ) -> bool:
        """Send a build-failure notification."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
            {"title": "Environment", "value": environment.upper(), "short": True},
        ]

        if step:
            fields.append({"title": "Failed Step", "value": step, "short": True})

        # Truncate long error messages for Slack display
        truncated_error = error[:500] + "..." if len(error) > 500 else error
        fields.append({"title": "Error", "value": f"```{truncated_error}```", "short": False})

        attachment = self._build_attachment(
            color=COLOR_FAILURE,
            title=":x: Build Failed",
            text=f"Server *{server_name}* build failed.",
            fields=fields,
            request_id=request_id,
        )

        return self.send_message({"attachments": [attachment]})

    # ------------------------------------------------------------------
    # Approval workflow notifications
    # ------------------------------------------------------------------

    def notify_approval_requested(
        self,
        server_name: str,
        environment: str,
        instance_size: str,
        requester: str,
        request_id: str,
    ) -> bool:
        """Send an approval-request notification with approve/reject buttons."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
            {"title": "Environment", "value": environment.upper(), "short": True},
            {"title": "Instance Size", "value": instance_size, "short": True},
            {"title": "Requested By", "value": requester, "short": True},
        ]

        # Determine why approval is required
        reasons = []
        if environment.lower() == "production":
            reasons.append("Production environment")
        if instance_size.lower() in ("xl", "2xl", "4xl", "xlarge", "2xlarge", "4xlarge"):
            reasons.append(f"Large instance ({instance_size})")
        reason_text = ", ".join(reasons) if reasons else "Policy requirement"
        fields.append({"title": "Reason", "value": reason_text, "short": False})

        attachment = self._build_attachment(
            color=COLOR_WARNING,
            title=":raised_hand: Approval Required",
            text=f"Server *{server_name}* requires approval before provisioning.",
            fields=fields,
            request_id=request_id,
        )

        # Add interactive buttons for approve/reject
        attachment["actions"] = [
            {
                "type": "button",
                "text": "Approve",
                "style": "primary",
                "name": "approval_action",
                "value": f"approve:{request_id}",
            },
            {
                "type": "button",
                "text": "Reject",
                "style": "danger",
                "name": "approval_action",
                "value": f"reject:{request_id}",
            },
        ]
        attachment["callback_id"] = f"server_approval:{request_id}"

        return self.send_message({"attachments": [attachment]})

    def notify_approval_granted(
        self,
        server_name: str,
        approver: str,
        request_id: str,
    ) -> bool:
        """Send an approval-granted notification."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
            {"title": "Approved By", "value": approver, "short": True},
        ]

        attachment = self._build_attachment(
            color=COLOR_SUCCESS,
            title=":white_check_mark: Approval Granted",
            text=f"Server *{server_name}* has been approved. Build will begin shortly.",
            fields=fields,
            request_id=request_id,
        )

        return self.send_message({"attachments": [attachment]})

    def notify_approval_rejected(
        self,
        server_name: str,
        approver: str,
        reason: str,
        request_id: str,
    ) -> bool:
        """Send an approval-rejected notification."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
            {"title": "Rejected By", "value": approver, "short": True},
        ]

        if reason:
            fields.append({"title": "Reason", "value": reason, "short": False})

        attachment = self._build_attachment(
            color=COLOR_FAILURE,
            title=":no_entry: Approval Rejected",
            text=f"Server *{server_name}* has been rejected.",
            fields=fields,
            request_id=request_id,
        )

        return self.send_message({"attachments": [attachment]})

    # ------------------------------------------------------------------
    # Decommission notifications
    # ------------------------------------------------------------------

    def notify_decommission_started(
        self,
        server_name: str,
        request_id: str,
    ) -> bool:
        """Send a decommission-started notification."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
        ]

        attachment = self._build_attachment(
            color=COLOR_DECOM,
            title=":wastebasket: Decommission Started",
            text=f"Server *{server_name}* is being decommissioned.",
            fields=fields,
            request_id=request_id,
        )

        return self.send_message({"attachments": [attachment]})

    def notify_decommission_completed(
        self,
        server_name: str,
        request_id: str,
    ) -> bool:
        """Send a decommission-completed notification."""
        fields = [
            {"title": "Server", "value": server_name, "short": True},
        ]

        attachment = self._build_attachment(
            color=COLOR_NEUTRAL,
            title=":heavy_check_mark: Decommission Completed",
            text=f"Server *{server_name}* has been fully decommissioned.",
            fields=fields,
            request_id=request_id,
        )

        return self.send_message({"attachments": [attachment]})

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_attachment(
        self,
        color: str,
        title: str,
        text: str,
        fields: list[dict],
        request_id: str,
    ) -> dict:
        """Build a Slack attachment with standard AnvilOps formatting.

        Each attachment includes:
        - Color-coded sidebar
        - Title with emoji prefix
        - Server detail fields
        - "View Details" link to the AnvilOps frontend
        - Footer with AnvilOps branding and UTC timestamp
        """
        request_url = f"{self.app_url}/requests/{request_id}"
        now = datetime.now(timezone.utc)

        return {
            "color": color,
            "title": title,
            "title_link": request_url,
            "text": text,
            "fields": fields,
            "actions": [
                {
                    "type": "button",
                    "text": "View Details",
                    "url": request_url,
                },
            ],
            "footer": "AnvilOps",
            "footer_icon": "",
            "ts": int(now.timestamp()),
            "mrkdwn_in": ["text", "fields"],
        }

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format duration as a human-readable string.

        Examples:
            45  -> "45s"
            125 -> "2m 5s"
            3661 -> "1h 1m 1s"
        """
        if seconds < 0:
            return "0s"

        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)

        parts: list[str] = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs or not parts:
            parts.append(f"{secs}s")

        return " ".join(parts)


def get_slack_notifier() -> SlackNotifier:
    """Create a SlackNotifier from application settings.

    This is the standard way to obtain a notifier instance throughout the
    application.  It reads from ``app.core.config.settings`` on every call
    so that runtime configuration changes are picked up.
    """
    from app.core.config import settings

    return SlackNotifier(
        webhook_url=settings.SLACK_WEBHOOK_URL,
        enabled=settings.SLACK_ENABLED,
        app_url=settings.SLACK_APP_URL,
        channel=settings.SLACK_CHANNEL,
    )
