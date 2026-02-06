"""Celery tasks for sending Slack notifications asynchronously.

Notifications are dispatched via Celery so they never block or slow down
the main build pipeline.  Every task is best-effort: failures are logged
but never re-raised.
"""

import logging

from app.worker.celery_app import celery_app
from app.services.slack import get_slack_notifier

logger = logging.getLogger(__name__)

# Map notification type strings to the corresponding SlackNotifier method name.
_DISPATCH_MAP: dict[str, str] = {
    "build_started": "notify_build_started",
    "build_completed": "notify_build_completed",
    "build_failed": "notify_build_failed",
    "approval_requested": "notify_approval_requested",
    "approval_granted": "notify_approval_granted",
    "approval_rejected": "notify_approval_rejected",
    "decommission_started": "notify_decommission_started",
    "decommission_completed": "notify_decommission_completed",
}


@celery_app.task(
    name="tasks.send_slack_notification",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
    soft_time_limit=30,
    ignore_result=True,
)
def send_slack_notification(self, notification_type: str, **kwargs) -> dict:
    """Send a Slack notification asynchronously via Celery.

    Parameters
    ----------
    notification_type:
        One of the keys in ``_DISPATCH_MAP`` (e.g. ``"build_started"``).
    **kwargs:
        Keyword arguments forwarded to the corresponding
        :class:`~app.services.slack.SlackNotifier` method.

    Returns
    -------
    dict
        ``{"status": "sent", "type": ...}`` on success,
        ``{"status": "skipped"|"failed"|"error", ...}`` otherwise.
    """
    method_name = _DISPATCH_MAP.get(notification_type)

    if method_name is None:
        logger.error("Unknown notification type: %r", notification_type)
        return {
            "status": "error",
            "type": notification_type,
            "detail": f"Unknown notification type: {notification_type}",
        }

    try:
        notifier = get_slack_notifier()
        method = getattr(notifier, method_name)
        success = method(**kwargs)

        if success:
            logger.info("Slack notification sent: %s", notification_type)
            return {"status": "sent", "type": notification_type}
        else:
            logger.info("Slack notification skipped/failed: %s", notification_type)
            return {"status": "skipped", "type": notification_type}

    except Exception as exc:
        logger.exception(
            "Failed to send Slack notification (%s): %s",
            notification_type,
            exc,
        )
        # Retry on transient errors (network timeouts, etc.)
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.warning(
                "Max retries exceeded for Slack notification: %s", notification_type
            )

        return {
            "status": "failed",
            "type": notification_type,
            "detail": str(exc)[:500],
        }
