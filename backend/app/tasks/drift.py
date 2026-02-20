"""Celery tasks for proactive drift detection and reporting.

Tasks:
  - poll_drift_events    -- Periodic task (every 5 minutes) to poll PuppetDB
                            for new corrective changes, store drift events,
                            generate alerts, and send notifications.
  - generate_drift_report -- Generate a daily drift summary report.
"""

import logging
from datetime import datetime, timezone

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _get_drift_monitor():
    """Construct a DriftMonitor instance.

    Lazy import to avoid circular dependencies and so the module
    loads even if Puppet service configuration is incomplete.
    """
    from app.services.drift_monitor import DriftMonitor
    return DriftMonitor()


# ---------------------------------------------------------------------------
# poll_drift_events
# ---------------------------------------------------------------------------


@celery_app.task(name="tasks.poll_drift_events")
def poll_drift_events() -> dict:
    """Periodic task to poll PuppetDB for new drift events.

    Designed to run every 5 minutes via Celery Beat.  On each run it:

    1. Queries PuppetDB for reports with corrective changes received
       in the last 10 minutes (overlapping window for reliability).
    2. Categorises each changed resource event by severity and drift type.
    3. Stores new DriftEvent records (deduplicated by report hash +
       resource).
    4. Checks for concerning drift patterns across affected servers.
    5. Generates DriftAlert records for significant events and patterns.
    6. Sends Slack and in-app notifications for critical/high alerts.

    Returns:
        A dict summarising the poll results: new_events (count),
        patterns_detected (count), alerts_generated (count).
    """
    logger.info("poll_drift_events starting")

    monitor = _get_drift_monitor()

    try:
        # Step 1-3: Poll and store drift events
        new_events = monitor.poll_drift_events(since_minutes=10)
        logger.info("Polled %d new drift events", len(new_events))

        # Step 4: Check patterns for each affected server
        affected_servers = {
            e["server_request_id"]
            for e in new_events
            if e.get("server_request_id")
        }

        all_patterns: list[dict] = []
        for server_id in affected_servers:
            try:
                patterns = monitor.check_drift_patterns(server_id)
                # Tag patterns with server_request_id for alert generation
                for p in patterns:
                    p.setdefault("details", {})["server_request_id"] = server_id
                all_patterns.extend(patterns)
            except Exception:
                logger.exception(
                    "Failed to check drift patterns for server %s", server_id
                )

        logger.info(
            "Detected %d drift patterns across %d servers",
            len(all_patterns), len(affected_servers),
        )

        # Step 5: Generate alerts
        alerts = monitor.generate_alerts(new_events, all_patterns)
        logger.info("Generated %d drift alerts", len(alerts))

        # Step 6: Send notifications
        if new_events or alerts:
            try:
                monitor.send_drift_notifications(new_events, alerts)
            except Exception:
                logger.exception("Failed to send drift notifications")

        result = {
            "status": "success",
            "new_events": len(new_events),
            "patterns_detected": len(all_patterns),
            "alerts_generated": len(alerts),
            "affected_servers": len(affected_servers),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("poll_drift_events completed: %s", result)
        return result

    except Exception as exc:
        logger.exception("poll_drift_events failed: %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "new_events": 0,
            "patterns_detected": 0,
            "alerts_generated": 0,
            "affected_servers": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# generate_drift_report
# ---------------------------------------------------------------------------


@celery_app.task(name="tasks.generate_drift_report")
def generate_drift_report() -> dict:
    """Generate a daily drift summary report.

    Designed to run once per day via Celery Beat.  Aggregates drift
    data from the last 24 hours into a summary suitable for daily
    reporting and Slack digest notifications.

    Returns:
        A dict with the drift summary data.
    """
    logger.info("generate_drift_report starting")

    try:
        from datetime import timedelta

        from sqlalchemy import distinct, func, select

        from app.models.drift import DriftAlert, DriftEvent
        from app.services.db import get_sync_db

        now = datetime.now(timezone.utc)
        cutoff_24h = now - timedelta(hours=24)

        with get_sync_db() as session:
            # New events in last 24h
            new_events_count = session.execute(
                select(func.count(DriftEvent.id))
                .where(DriftEvent.detected_at >= cutoff_24h)
            ).scalar() or 0

            # Unresolved events total
            unresolved_count = session.execute(
                select(func.count(DriftEvent.id))
                .where(DriftEvent.is_resolved == False)  # noqa: E712
            ).scalar() or 0

            # Auto-corrected in last 24h
            auto_corrected = session.execute(
                select(func.count(DriftEvent.id))
                .where(
                    DriftEvent.detected_at >= cutoff_24h,
                    DriftEvent.is_corrective == True,  # noqa: E712
                )
            ).scalar() or 0

            # Events by severity in last 24h
            severity_result = session.execute(
                select(
                    DriftEvent.severity,
                    func.count(DriftEvent.id).label("count"),
                )
                .where(DriftEvent.detected_at >= cutoff_24h)
                .group_by(DriftEvent.severity)
            )
            by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            for row in severity_result:
                if row.severity in by_severity:
                    by_severity[row.severity] = row.count

            # Events by category in last 24h
            category_result = session.execute(
                select(
                    DriftEvent.drift_category,
                    func.count(DriftEvent.id).label("count"),
                )
                .where(DriftEvent.detected_at >= cutoff_24h)
                .group_by(DriftEvent.drift_category)
            )
            by_category = {
                "security": 0, "configuration": 0, "package": 0,
                "service": 0, "file": 0,
            }
            for row in category_result:
                if row.drift_category in by_category:
                    by_category[row.drift_category] = row.count

            # Affected servers in last 24h
            affected = session.execute(
                select(func.count(distinct(DriftEvent.certname)))
                .where(DriftEvent.detected_at >= cutoff_24h)
            ).scalar() or 0

            # Active alerts
            active_alerts = session.execute(
                select(func.count(DriftAlert.id))
                .where(DriftAlert.is_acknowledged == False)  # noqa: E712
            ).scalar() or 0

            # Top drifting resources in last 24h
            top_resources_result = session.execute(
                select(
                    DriftEvent.resource_type,
                    DriftEvent.resource_title,
                    func.count(DriftEvent.id).label("count"),
                )
                .where(DriftEvent.detected_at >= cutoff_24h)
                .group_by(DriftEvent.resource_type, DriftEvent.resource_title)
                .order_by(func.count(DriftEvent.id).desc())
                .limit(10)
            )
            top_resources = [
                {
                    "resource": f"{row.resource_type}[{row.resource_title}]",
                    "count": row.count,
                }
                for row in top_resources_result
            ]

        report = {
            "status": "success",
            "report_date": now.strftime("%Y-%m-%d"),
            "period_hours": 24,
            "new_events": new_events_count,
            "unresolved_total": unresolved_count,
            "auto_corrected": auto_corrected,
            "by_severity": by_severity,
            "by_category": by_category,
            "affected_servers": affected,
            "active_alerts": active_alerts,
            "top_resources": top_resources,
            "generated_at": now.isoformat(),
        }

        logger.info("Daily drift report generated: %s", report)

        # Send Slack digest if there were any events
        if new_events_count > 0:
            _send_daily_digest_slack(report)

        # Create in-app notification for the report
        _send_daily_digest_notification(report)

        return report

    except Exception as exc:
        logger.exception("generate_drift_report failed: %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def _send_daily_digest_slack(report: dict) -> None:
    """Send a daily drift digest to Slack. Best-effort."""
    try:
        from app.services.slack import get_slack_notifier

        notifier = get_slack_notifier()

        severity = report.get("by_severity", {})

        fields = [
            {
                "title": "New Events (24h)",
                "value": str(report.get("new_events", 0)),
                "short": True,
            },
            {
                "title": "Unresolved Total",
                "value": str(report.get("unresolved_total", 0)),
                "short": True,
            },
            {
                "title": "Auto-Corrected",
                "value": str(report.get("auto_corrected", 0)),
                "short": True,
            },
            {
                "title": "Affected Servers",
                "value": str(report.get("affected_servers", 0)),
                "short": True,
            },
            {
                "title": "Active Alerts",
                "value": str(report.get("active_alerts", 0)),
                "short": True,
            },
            {
                "title": "By Severity",
                "value": (
                    f"Critical: {severity.get('critical', 0)} | "
                    f"High: {severity.get('high', 0)} | "
                    f"Medium: {severity.get('medium', 0)} | "
                    f"Low: {severity.get('low', 0)}"
                ),
                "short": False,
            },
        ]

        # Determine color based on severity
        if severity.get("critical", 0) > 0:
            color = "#F44336"  # Red
        elif severity.get("high", 0) > 0:
            color = "#FFC107"  # Yellow
        else:
            color = "#4CAF50"  # Green

        payload = {
            "attachments": [{
                "color": color,
                "title": f":bar_chart: Daily Drift Report - {report.get('report_date', 'Unknown')}",
                "text": (
                    f"*{report.get('new_events', 0)}* drift events detected "
                    f"in the last 24 hours across "
                    f"*{report.get('affected_servers', 0)}* servers."
                ),
                "fields": fields,
                "footer": "AnvilOps Drift Monitor",
                "ts": int(datetime.now(timezone.utc).timestamp()),
                "mrkdwn_in": ["text", "fields"],
            }],
        }

        notifier.send_message(payload)
    except Exception:
        logger.exception("Failed to send daily drift digest to Slack")


def _send_daily_digest_notification(report: dict) -> None:
    """Create an in-app notification for the daily drift report. Best-effort."""
    try:
        from app.services.notifications import NotificationService

        new_events = report.get("new_events", 0)
        unresolved = report.get("unresolved_total", 0)

        if new_events == 0 and unresolved == 0:
            # No drift to report -- skip notification
            return

        severity_level = "info"
        by_severity = report.get("by_severity", {})
        if by_severity.get("critical", 0) > 0:
            severity_level = "error"
        elif by_severity.get("high", 0) > 0:
            severity_level = "warning"

        NotificationService.create_sync(
            title=f"Daily Drift Report - {report.get('report_date', 'Unknown')}",
            message=(
                f"{new_events} drift events detected in the last 24 hours. "
                f"{unresolved} total unresolved events across fleet."
            ),
            user_email="all",
            category="compliance",
            severity=severity_level,
            resource_type="drift_report",
            action_url="/drift",
            icon="bar-chart",
            details=report,
        )
    except Exception:
        logger.exception("Failed to send daily drift digest notification")


# ---------------------------------------------------------------------------
# Celery Beat schedule entry (to be merged into celery config)
# ---------------------------------------------------------------------------
# Add the following to your celery beat schedule configuration:
#
# celery_app.conf.beat_schedule = {
#     "poll-drift-events": {
#         "task": "tasks.poll_drift_events",
#         "schedule": 300.0,  # Every 5 minutes
#     },
#     "generate-drift-report": {
#         "task": "tasks.generate_drift_report",
#         "schedule": crontab(hour=6, minute=0),  # Daily at 6 AM UTC
#     },
# }
