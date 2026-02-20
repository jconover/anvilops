"""Proactive drift detection and monitoring service.

Polls PuppetDB for report events, categorises drift, tracks severity,
and generates alerts for significant drift patterns.

This service is designed to be called from both:
  - Celery periodic tasks (sync, via DriftMonitor)
  - FastAPI endpoints (async, via AsyncDriftMonitor)
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drift import DriftAlert, DriftEvent
from app.models.server import ServerRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Drift categorisation rules
# ---------------------------------------------------------------------------

# Resource patterns mapped to (category, severity, cis_control_id).
# Checked in order; first match wins.
_CATEGORISATION_RULES: list[
    tuple[
        list[str],      # resource_type patterns (case-insensitive substring)
        list[str],      # resource_title patterns (case-insensitive substring)
        list[str],      # property_name patterns (case-insensitive substring)
        str,            # category
        str,            # severity
        str | None,     # cis_control_id
    ]
] = [
    # SSH configuration changes -- critical security
    (["file"], ["/etc/ssh/sshd_config", "sshd_config"], [],
     "security", "critical", "CIS-5.2.8"),
    # Firewall / iptables -- critical security
    (["file"], ["/etc/sysconfig/iptables", "iptables", "firewalld", "nftables",
                "windows_firewall"], [],
     "security", "critical", "CIS-3.5.1"),
    # Audit configuration -- critical security
    (["file"], ["/etc/audit/auditd.conf", "/etc/audit/rules.d", "auditd",
                "audit.rules"], [],
     "security", "critical", "CIS-4.1.1"),
    # PAM / password policy
    (["file"], ["/etc/pam.d", "/etc/security/pwquality", "/etc/login.defs"], [],
     "security", "critical", "CIS-5.3.1"),
    # Sudoers
    (["file"], ["/etc/sudoers", "/etc/sudoers.d"], [],
     "security", "high", "CIS-5.2.1"),
    # Windows security policy
    (["file"], ["secpol", "secedit", "gpo", "group_policy"], [],
     "security", "critical", None),
    # Generic security-type resources
    (["augeas", "selinux"], [], [],
     "security", "high", None),

    # Service state changes -- high
    (["service"], [], [],
     "service", "high", None),
    # Windows service
    (["windows_service"], [], [],
     "service", "high", None),

    # Package changes -- medium
    (["package"], [], [],
     "package", "medium", None),
    (["windows_package", "chocolatey_package"], [], [],
     "package", "medium", None),

    # Registry keys (Windows)
    (["registry_key", "registry_value"], [], [],
     "configuration", "medium", None),

    # Cron / scheduled tasks
    (["cron", "scheduled_task"], [], [],
     "configuration", "medium", None),

    # Generic file changes
    (["file"], [], ["content"],
     "file", "medium", None),
    (["file"], [], ["ensure"],
     "file", "medium", None),
    (["file"], [], ["mode", "owner", "group"],
     "file", "medium", None),
    (["file"], [], [],
     "file", "low", None),
]


def categorize_drift(
    resource_type: str,
    resource_title: str,
    property_name: str,
) -> tuple[str, str, str | None]:
    """Categorise a drift event into (category, severity, cis_control_id).

    Categories: security, configuration, package, service, file
    Severity rules:
      - SSH/firewall/audit config changes = critical
      - Service state changes = high
      - Package changes = medium
      - File content changes = medium
      - Other = low

    Returns:
        A 3-tuple of (category, severity, cis_control_id).
    """
    rt_lower = resource_type.lower()
    title_lower = resource_title.lower()
    prop_lower = property_name.lower()

    for (rt_pats, title_pats, prop_pats, category, severity, cis_id) in _CATEGORISATION_RULES:
        # Check resource_type patterns
        if rt_pats and not any(p.lower() in rt_lower for p in rt_pats):
            continue

        # Check resource_title patterns (if specified, at least one must match)
        if title_pats and not any(p.lower() in title_lower for p in title_pats):
            continue

        # Check property_name patterns (if specified, at least one must match)
        if prop_pats and not any(p.lower() in prop_lower for p in prop_pats):
            continue

        return category, severity, cis_id

    # Default: configuration / low / no CIS mapping
    return "configuration", "low", None


# ---------------------------------------------------------------------------
# Synchronous DriftMonitor (for Celery tasks)
# ---------------------------------------------------------------------------


class DriftMonitor:
    """Proactive drift detection service (synchronous, for Celery workers).

    Polls PuppetDB for corrective-change report events across all managed
    nodes, categorises each drift event, persists them to the database,
    detects concerning drift patterns, and generates alerts.
    """

    def __init__(self, puppet_service: Any | None = None) -> None:
        """
        Args:
            puppet_service: An optional PuppetEnterpriseServiceSync instance.
                If None, one will be created from application settings.
        """
        self._puppet = puppet_service

    def _get_puppet(self) -> Any:
        """Lazily obtain a PuppetEnterpriseServiceSync client."""
        if self._puppet is None:
            from app.services.puppet import PuppetEnterpriseServiceSync
            self._puppet = PuppetEnterpriseServiceSync()
        return self._puppet

    # -- PuppetDB polling ---------------------------------------------------

    def poll_drift_events(self, since_minutes: int = 10) -> list[dict]:
        """Poll PuppetDB for new corrective changes across all managed nodes.

        Queries PuppetDB for reports received within the last
        ``since_minutes`` that contain corrective or changed events,
        extracts individual resource events, and stores new DriftEvent
        records.

        Returns:
            List of dicts representing newly created drift events.
        """
        puppet = self._get_puppet()
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        # Query PuppetDB for reports with corrective changes in the window.
        # PQL: reports { receive_time > "cutoff" and corrective_change = true }
        url = puppet._puppetdb_url("/reports")
        query = [
            "and",
            [">", "receive_time", cutoff_iso],
            ["or",
                ["=", "corrective_change", True],
                ["=", "status", "changed"],
            ],
        ]

        try:
            response = puppet._post(url, json_body={"query": query})
            reports = response.json()
        except Exception:
            logger.exception("Failed to poll PuppetDB for drift reports")
            return []

        if not reports:
            logger.debug("No new drift reports found since %s", cutoff_iso)
            return []

        logger.info(
            "Found %d reports with potential drift since %s",
            len(reports), cutoff_iso,
        )

        # Build a certname -> server_request_id mapping
        from app.services.db import get_sync_db
        certname_to_server: dict[str, dict] = {}
        with get_sync_db() as session:
            result = session.execute(
                select(
                    ServerRequest.id,
                    ServerRequest.puppet_certname,
                    ServerRequest.server_name,
                ).where(
                    ServerRequest.puppet_certname.isnot(None),
                    ServerRequest.status == "ready",
                )
            )
            for row in result:
                if row.puppet_certname:
                    certname_to_server[row.puppet_certname] = {
                        "server_request_id": str(row.id),
                        "server_name": row.server_name,
                    }

        new_events: list[dict] = []

        for report in reports:
            certname = report.get("certname", "")
            if certname not in certname_to_server:
                logger.debug(
                    "Skipping drift report for unmanaged node %s", certname
                )
                continue

            server_info = certname_to_server[certname]
            report_hash = report.get("hash", "")
            report_time_str = report.get("receive_time", "")

            try:
                report_time = datetime.fromisoformat(
                    report_time_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                report_time = datetime.now(timezone.utc)

            # Fetch individual events for this report
            events = self._get_report_events(puppet, report_hash)

            for event in events:
                resource_type = event.get("resource_type", "Unknown")
                resource_title = event.get("resource_title", "unknown")
                property_name = event.get("property", "unknown")
                old_value = self._safe_str(event.get("old_value"))
                new_value = self._safe_str(event.get("new_value"))
                is_corrective = event.get("corrective_change", False)

                category, severity, cis_id = categorize_drift(
                    resource_type, resource_title, property_name
                )

                new_events.append({
                    "server_request_id": server_info["server_request_id"],
                    "certname": certname,
                    "detected_at": report_time,
                    "resource_type": resource_type,
                    "resource_title": resource_title,
                    "property_name": property_name,
                    "old_value": old_value,
                    "new_value": new_value,
                    "severity": severity,
                    "is_corrective": is_corrective,
                    "is_resolved": is_corrective,
                    "resolution_type": "auto_corrected" if is_corrective else None,
                    "resolved_at": report_time if is_corrective else None,
                    "drift_category": category,
                    "cis_control_id": cis_id,
                    "report_hash": report_hash,
                    "server_name": server_info["server_name"],
                })

        # Persist new events (deduplicate by report_hash + resource)
        stored_events = self._store_events(new_events)
        logger.info(
            "Stored %d new drift events from %d reports",
            len(stored_events), len(reports),
        )

        return stored_events

    def _get_report_events(self, puppet: Any, report_hash: str) -> list[dict]:
        """Fetch individual resource events for a specific report.

        GET /pdb/query/v4/events?query=["=","report","<hash>"]
        """
        if not report_hash:
            return []

        url = puppet._puppetdb_url("/events")
        query = ["=", "report", report_hash]
        try:
            response = puppet._post(url, json_body={"query": query})
            events = response.json()
            # Filter to only changed/failed events (skip noop, skipped, etc.)
            return [
                e for e in events
                if e.get("status") in ("success", "failure")
            ]
        except Exception:
            logger.warning(
                "Failed to fetch events for report %s", report_hash
            )
            return []

    def _store_events(self, events: list[dict]) -> list[dict]:
        """Persist new drift events to the database, deduplicating."""
        if not events:
            return []

        from app.services.db import get_sync_db

        stored: list[dict] = []

        with get_sync_db() as session:
            # Load existing report_hash values for dedup
            report_hashes = {e["report_hash"] for e in events if e.get("report_hash")}
            existing_hashes: set[str] = set()

            if report_hashes:
                result = session.execute(
                    select(
                        DriftEvent.report_hash,
                        DriftEvent.resource_title,
                        DriftEvent.property_name,
                    ).where(DriftEvent.report_hash.in_(report_hashes))
                )
                for row in result:
                    existing_hashes.add(
                        f"{row.report_hash}:{row.resource_title}:{row.property_name}"
                    )

            for event_data in events:
                dedup_key = (
                    f"{event_data.get('report_hash')}:"
                    f"{event_data['resource_title']}:"
                    f"{event_data['property_name']}"
                )
                if dedup_key in existing_hashes:
                    continue

                event = DriftEvent(
                    id=uuid4(),
                    server_request_id=event_data["server_request_id"],
                    certname=event_data["certname"],
                    detected_at=event_data["detected_at"],
                    resolved_at=event_data.get("resolved_at"),
                    resource_type=event_data["resource_type"],
                    resource_title=event_data["resource_title"],
                    property_name=event_data["property_name"],
                    old_value=event_data.get("old_value"),
                    new_value=event_data.get("new_value"),
                    severity=event_data["severity"],
                    is_corrective=event_data["is_corrective"],
                    is_resolved=event_data.get("is_resolved", False),
                    resolution_type=event_data.get("resolution_type"),
                    drift_category=event_data["drift_category"],
                    cis_control_id=event_data.get("cis_control_id"),
                    report_hash=event_data.get("report_hash"),
                )
                session.add(event)
                existing_hashes.add(dedup_key)

                stored.append({
                    "id": str(event.id),
                    "certname": event_data["certname"],
                    "server_name": event_data.get("server_name", ""),
                    "resource_type": event_data["resource_type"],
                    "resource_title": event_data["resource_title"],
                    "severity": event_data["severity"],
                    "drift_category": event_data["drift_category"],
                    "is_corrective": event_data["is_corrective"],
                })

            session.flush()

        return stored

    @staticmethod
    def _safe_str(value: Any) -> str | None:
        """Safely convert a value to a string for storage."""
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, default=str)
            except (TypeError, ValueError):
                return str(value)
        return str(value)

    # -- Pattern detection --------------------------------------------------

    def check_drift_patterns(self, server_id: str) -> list[dict]:
        """Detect concerning drift patterns for a server.

        Patterns checked:
          - Same resource drifting repeatedly (>3 times in 24h)
          - Multiple resources drifting simultaneously (>=5 in 1h)
          - Compliance score dropping (many unresolved events)

        Returns:
            List of pattern dicts with keys: pattern_type, severity,
            title, message, details.
        """
        from app.services.db import get_sync_db

        patterns: list[dict] = []
        now = datetime.now(timezone.utc)

        with get_sync_db() as session:
            # Pattern 1: Same resource drifting > 3 times in 24h
            cutoff_24h = now - timedelta(hours=24)
            repeat_result = session.execute(
                select(
                    DriftEvent.resource_type,
                    DriftEvent.resource_title,
                    DriftEvent.property_name,
                    func.count(DriftEvent.id).label("count"),
                )
                .where(
                    DriftEvent.server_request_id == server_id,
                    DriftEvent.detected_at >= cutoff_24h,
                )
                .group_by(
                    DriftEvent.resource_type,
                    DriftEvent.resource_title,
                    DriftEvent.property_name,
                )
                .having(func.count(DriftEvent.id) > 3)
            )

            for row in repeat_result:
                patterns.append({
                    "pattern_type": "repeated_drift",
                    "severity": "high",
                    "title": f"Repeated drift: {row.resource_type}[{row.resource_title}]",
                    "message": (
                        f"Resource {row.resource_type}[{row.resource_title}] "
                        f"property '{row.property_name}' has drifted "
                        f"{row.count} times in the last 24 hours. "
                        f"This may indicate a persistent configuration conflict."
                    ),
                    "details": {
                        "resource_type": row.resource_type,
                        "resource_title": row.resource_title,
                        "property_name": row.property_name,
                        "count": row.count,
                        "period_hours": 24,
                    },
                })

            # Pattern 2: Multiple simultaneous drifts (>=5 in 1h)
            cutoff_1h = now - timedelta(hours=1)
            simultaneous_result = session.execute(
                select(func.count(DriftEvent.id).label("count"))
                .where(
                    DriftEvent.server_request_id == server_id,
                    DriftEvent.detected_at >= cutoff_1h,
                )
            )
            recent_count = simultaneous_result.scalar() or 0

            if recent_count >= 5:
                patterns.append({
                    "pattern_type": "simultaneous_drift",
                    "severity": "critical",
                    "title": "Multiple simultaneous drifts detected",
                    "message": (
                        f"{recent_count} drift events detected in the last hour. "
                        f"This may indicate a major configuration change or "
                        f"unauthorized access."
                    ),
                    "details": {
                        "count": recent_count,
                        "period_hours": 1,
                    },
                })

            # Pattern 3: High number of unresolved drift events
            unresolved_result = session.execute(
                select(func.count(DriftEvent.id).label("count"))
                .where(
                    DriftEvent.server_request_id == server_id,
                    DriftEvent.is_resolved == False,  # noqa: E712
                )
            )
            unresolved_count = unresolved_result.scalar() or 0

            if unresolved_count >= 10:
                patterns.append({
                    "pattern_type": "compliance_drop",
                    "severity": "critical",
                    "title": "Compliance drop: many unresolved drift events",
                    "message": (
                        f"{unresolved_count} unresolved drift events detected. "
                        f"Server compliance may be significantly degraded."
                    ),
                    "details": {
                        "unresolved_count": unresolved_count,
                    },
                })
            elif unresolved_count >= 5:
                patterns.append({
                    "pattern_type": "compliance_drop",
                    "severity": "high",
                    "title": "Compliance warning: growing unresolved drift",
                    "message": (
                        f"{unresolved_count} unresolved drift events detected. "
                        f"Investigate and remediate to maintain compliance."
                    ),
                    "details": {
                        "unresolved_count": unresolved_count,
                    },
                })

        return patterns

    # -- Alert generation ---------------------------------------------------

    def generate_alerts(
        self,
        events: list[dict],
        patterns: list[dict],
    ) -> list[dict]:
        """Create DriftAlert records for significant drift events and patterns.

        Args:
            events: List of newly stored drift event dicts.
            patterns: List of detected pattern dicts.

        Returns:
            List of created alert dicts.
        """
        from app.services.db import get_sync_db

        alerts: list[dict] = []

        with get_sync_db() as session:
            # Generate alerts for critical/high severity new events
            for event in events:
                if event.get("severity") not in ("critical", "high"):
                    continue

                alert = DriftAlert(
                    id=uuid4(),
                    drift_event_id=event.get("id"),
                    server_request_id=None,
                    alert_type="drift_detected",
                    severity=event["severity"],
                    title=(
                        f"Drift detected: {event['resource_type']}"
                        f"[{event['resource_title']}]"
                    ),
                    message=(
                        f"{event['severity'].upper()} drift on "
                        f"{event.get('server_name', event['certname'])}: "
                        f"{event['resource_type']}[{event['resource_title']}] "
                        f"({event['drift_category']})"
                    ),
                )
                session.add(alert)
                alerts.append({
                    "id": str(alert.id),
                    "alert_type": "drift_detected",
                    "severity": event["severity"],
                    "title": alert.title,
                })

            # Generate alerts from patterns
            for pattern in patterns:
                server_id = pattern.get("details", {}).get("server_request_id")

                # Check if we already have an unacknowledged alert of this type
                # for this pattern (avoid alert spam)
                existing = session.execute(
                    select(DriftAlert.id).where(
                        DriftAlert.alert_type == pattern["pattern_type"],
                        DriftAlert.is_acknowledged == False,  # noqa: E712
                        DriftAlert.title == pattern["title"],
                    ).limit(1)
                ).scalar_one_or_none()

                if existing:
                    continue

                alert = DriftAlert(
                    id=uuid4(),
                    drift_event_id=None,
                    server_request_id=server_id,
                    alert_type=pattern["pattern_type"],
                    severity=pattern["severity"],
                    title=pattern["title"][:200],
                    message=pattern["message"],
                )
                session.add(alert)
                alerts.append({
                    "id": str(alert.id),
                    "alert_type": pattern["pattern_type"],
                    "severity": pattern["severity"],
                    "title": pattern["title"],
                })

            session.flush()

        if alerts:
            logger.info("Generated %d drift alerts", len(alerts))

        return alerts

    # -- Notification dispatch ----------------------------------------------

    def send_drift_notifications(self, events: list[dict], alerts: list[dict]) -> None:
        """Send Slack and in-app notifications for significant drift.

        Best-effort: failures are logged but do not propagate.
        """
        # In-app notifications
        try:
            from app.services.notifications import NotificationService

            for alert_data in alerts:
                NotificationService.create_sync(
                    title=alert_data["title"],
                    message=alert_data.get("message", alert_data["title"]),
                    user_email="all",
                    category="compliance",
                    severity=_map_severity_to_notification(alert_data["severity"]),
                    resource_type="drift_alert",
                    resource_id=alert_data.get("id"),
                    action_url="/drift",
                    icon="shield-alert",
                    details={
                        "alert_type": alert_data["alert_type"],
                        "severity": alert_data["severity"],
                    },
                )
        except Exception:
            logger.exception("Failed to send in-app drift notifications")

        # Slack notifications for critical/high alerts
        try:
            from app.services.slack import get_slack_notifier

            notifier = get_slack_notifier()
            critical_alerts = [
                a for a in alerts if a.get("severity") in ("critical", "high")
            ]

            for alert_data in critical_alerts:
                sev = alert_data["severity"]
                severity_emoji = ":rotating_light:" if sev == "critical" else ":warning:"
                payload = {
                    "attachments": [{
                        "color": "#F44336" if alert_data["severity"] == "critical" else "#FFC107",
                        "title": f"{severity_emoji} {alert_data['title']}",
                        "text": alert_data.get("message", ""),
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert_data["severity"].upper(),
                                "short": True,
                            },
                            {
                                "title": "Type",
                                "value": alert_data["alert_type"],
                                "short": True,
                            },
                        ],
                        "footer": "AnvilOps Drift Monitor",
                        "ts": int(datetime.now(timezone.utc).timestamp()),
                    }],
                }
                notifier.send_message(payload)
        except Exception:
            logger.exception("Failed to send Slack drift notifications")


# ---------------------------------------------------------------------------
# Async DriftMonitor (for FastAPI endpoints)
# ---------------------------------------------------------------------------


class AsyncDriftMonitor:
    """Async drift query service for FastAPI endpoints.

    Reads drift data from the database. PuppetDB polling is handled
    exclusively by the Celery periodic task using the sync DriftMonitor.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_drift_summary(self) -> dict:
        """Fleet-wide drift summary.

        Returns:
            Dict with total_events, unresolved_events, resolved_events,
            auto_corrected, active_alerts, affected_servers, by_severity,
            by_category, and generated_at.
        """
        now = datetime.now(timezone.utc)

        # Total events
        total_result = await self.db.execute(
            select(func.count(DriftEvent.id))
        )
        total_events = total_result.scalar() or 0

        # Unresolved events
        unresolved_result = await self.db.execute(
            select(func.count(DriftEvent.id))
            .where(DriftEvent.is_resolved == False)  # noqa: E712
        )
        unresolved_events = unresolved_result.scalar() or 0

        # Auto-corrected events
        auto_result = await self.db.execute(
            select(func.count(DriftEvent.id))
            .where(DriftEvent.is_corrective == True)  # noqa: E712
        )
        auto_corrected = auto_result.scalar() or 0

        # Active (unacknowledged) alerts
        alerts_result = await self.db.execute(
            select(func.count(DriftAlert.id))
            .where(DriftAlert.is_acknowledged == False)  # noqa: E712
        )
        active_alerts = alerts_result.scalar() or 0

        # Distinct affected servers
        servers_result = await self.db.execute(
            select(func.count(distinct(DriftEvent.certname)))
        )
        affected_servers = servers_result.scalar() or 0

        # By severity
        severity_result = await self.db.execute(
            select(
                DriftEvent.severity,
                func.count(DriftEvent.id).label("count"),
            )
            .group_by(DriftEvent.severity)
        )
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for row in severity_result:
            if row.severity in by_severity:
                by_severity[row.severity] = row.count

        # By category
        category_result = await self.db.execute(
            select(
                DriftEvent.drift_category,
                func.count(DriftEvent.id).label("count"),
            )
            .group_by(DriftEvent.drift_category)
        )
        by_category = {
            "security": 0, "configuration": 0, "package": 0,
            "service": 0, "file": 0,
        }
        for row in category_result:
            if row.drift_category in by_category:
                by_category[row.drift_category] = row.count

        return {
            "total_events": total_events,
            "unresolved_events": unresolved_events,
            "resolved_events": total_events - unresolved_events,
            "auto_corrected": auto_corrected,
            "active_alerts": active_alerts,
            "affected_servers": affected_servers,
            "by_severity": by_severity,
            "by_category": by_category,
            "generated_at": now,
        }

    async def get_drift_events(
        self,
        *,
        server_id: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        is_resolved: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """List drift events with filtering and pagination.

        Returns:
            Dict with events, total, page, page_size.
        """
        conditions = []
        if server_id:
            conditions.append(DriftEvent.server_request_id == server_id)
        if severity:
            conditions.append(DriftEvent.severity == severity)
        if category:
            conditions.append(DriftEvent.drift_category == category)
        if is_resolved is not None:
            conditions.append(DriftEvent.is_resolved == is_resolved)
        if date_from:
            conditions.append(DriftEvent.detected_at >= date_from)
        if date_to:
            conditions.append(DriftEvent.detected_at <= date_to)

        # Count total
        count_query = select(func.count(DriftEvent.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Fetch page
        query = (
            select(DriftEvent)
            .order_by(DriftEvent.detected_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.db.execute(query)
        events = result.scalars().all()

        return {
            "events": events,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_drift_event_by_id(self, event_id: str) -> DriftEvent | None:
        """Fetch a single drift event by ID."""
        result = await self.db.execute(
            select(DriftEvent).where(DriftEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_server_drift_timeline(
        self, server_id: str, hours: int = 168
    ) -> dict:
        """Get drift events for a server over time for timeline visualisation.

        Args:
            server_id: UUID of the server request.
            hours: Lookback period in hours (default 7 days / 168 hours).

        Returns:
            Dict with server_request_id, certname, period_hours,
            events (list), and total.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Get server's certname
        server_result = await self.db.execute(
            select(ServerRequest.puppet_certname)
            .where(ServerRequest.id == server_id)
        )
        certname = server_result.scalar_one_or_none() or ""

        # Fetch events
        result = await self.db.execute(
            select(DriftEvent)
            .where(
                DriftEvent.server_request_id == server_id,
                DriftEvent.detected_at >= cutoff,
            )
            .order_by(DriftEvent.detected_at.desc())
        )
        events = result.scalars().all()

        return {
            "server_request_id": server_id,
            "certname": certname,
            "period_hours": hours,
            "events": events,
            "total": len(events),
        }

    async def get_drift_alerts(
        self,
        *,
        is_acknowledged: bool | None = None,
        severity: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """List drift alerts with filtering and pagination."""
        conditions = []
        if is_acknowledged is not None:
            conditions.append(DriftAlert.is_acknowledged == is_acknowledged)
        if severity:
            conditions.append(DriftAlert.severity == severity)

        count_query = select(func.count(DriftAlert.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = (
            select(DriftAlert)
            .order_by(DriftAlert.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        if conditions:
            query = query.where(and_(*conditions))

        result = await self.db.execute(query)
        alerts = result.scalars().all()

        return {
            "alerts": alerts,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def acknowledge_alert(
        self, alert_id: str, acknowledged_by: str
    ) -> DriftAlert | None:
        """Acknowledge a drift alert.

        Returns:
            The updated DriftAlert, or None if not found.
        """
        result = await self.db.execute(
            select(DriftAlert).where(DriftAlert.id == alert_id)
        )
        alert = result.scalar_one_or_none()

        if alert is None:
            return None

        alert.is_acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.updated_at = datetime.now(timezone.utc)

        await self.db.flush()
        return alert

    async def get_drift_trends(self, days: int = 30) -> dict:
        """Get drift trending data -- events per day, per category.

        Returns:
            Dict with period_days, daily (list of per-day dicts),
            and generated_at.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(DriftEvent)
            .where(DriftEvent.detected_at >= cutoff)
            .order_by(DriftEvent.detected_at.asc())
        )
        events = result.scalars().all()

        # Bucket events by day and category
        daily_buckets: dict[str, dict[str, int]] = defaultdict(
            lambda: {
                "total": 0, "security": 0, "configuration": 0,
                "package": 0, "service": 0, "file": 0,
            }
        )

        for event in events:
            day_key = event.detected_at.strftime("%Y-%m-%d")
            daily_buckets[day_key]["total"] += 1
            cat = event.drift_category
            if cat in daily_buckets[day_key]:
                daily_buckets[day_key][cat] += 1

        # Fill in missing days with zeros
        daily: list[dict] = []
        current = cutoff.date()
        today = datetime.now(timezone.utc).date()
        while current <= today:
            day_str = current.isoformat()
            bucket = daily_buckets.get(day_str, {
                "total": 0, "security": 0, "configuration": 0,
                "package": 0, "service": 0, "file": 0,
            })
            daily.append({"date": day_str, **bucket})
            current += timedelta(days=1)

        return {
            "period_days": days,
            "daily": daily,
            "generated_at": datetime.now(timezone.utc),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _map_severity_to_notification(severity: str) -> str:
    """Map drift severity to notification severity level."""
    mapping = {
        "critical": "error",
        "high": "warning",
        "medium": "info",
        "low": "info",
    }
    return mapping.get(severity, "info")
