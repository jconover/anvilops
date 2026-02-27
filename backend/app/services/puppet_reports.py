"""Puppet compliance reporting and analytics service.

Aggregates data from PuppetDB (via PuppetEnterpriseServiceSync) into
compliance summaries, per-node detail, and drift reports suitable for
dashboards and audit exports.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from app.services.puppet import PuppetEnterpriseServiceSync

logger = logging.getLogger(__name__)


class ResourceCounts(TypedDict):
    """Resource-level metrics from a Puppet report."""

    total: int
    changed: int
    failed: int
    skipped: int


class NodeCompliance(TypedDict):
    """Compliance status for a single Puppet node."""

    certname: str
    status: str
    last_report_time: str | None
    last_report_status: str
    resource_counts: ResourceCounts
    corrective_changes: int
    uptime_hours: float | None
    puppet_version: str | None
    environment: str


class FleetCompliance(TypedDict):
    """Compliance summary across a fleet of Puppet nodes."""

    total: int
    compliant: int
    changed: int
    failed: int
    unresponsive: int
    compliance_rate: float
    nodes: list[NodeCompliance]


class NodeDriftReport(TypedDict):
    """Drift report for a single node over a time period."""

    certname: str
    period_hours: int
    total_runs: int
    drift_events: int
    resources_corrected: list[str]


class PuppetComplianceService:
    """Aggregates Puppet report data for compliance dashboards."""

    def __init__(self, puppet_service: PuppetEnterpriseServiceSync) -> None:
        """
        Args:
            puppet_service: PuppetEnterpriseServiceSync instance providing
                get_node_status(), get_node_report(), and get_node_facts().
        """
        self.puppet = puppet_service

    # ------------------------------------------------------------------
    # Single-node compliance
    # ------------------------------------------------------------------

    def get_node_compliance(self, certname: str) -> NodeCompliance:
        """Get compliance status for a single node.

        Queries PuppetDB for the node's latest status, report, and facts,
        then normalises them into a single compliance dict.

        Returns:
            {
                "certname": str,
                "status": "compliant" | "changed" | "failed" | "unresponsive",
                "last_report_time": str | None,
                "last_report_status": str,
                "resource_counts": {
                    "total": int, "changed": int, "failed": int, "skipped": int
                },
                "corrective_changes": int,
                "uptime_hours": float | None,
                "puppet_version": str | None,
                "environment": str,
            }
        """
        # Fetch node status from PuppetDB
        node_status = self.puppet.get_node_status(certname)

        last_report_time: str | None = node_status.get("report_timestamp")
        report_status: str | None = node_status.get("latest_report_status")
        environment: str = node_status.get("report_environment", "production")
        puppet_version: str | None = node_status.get("catalog_environment")

        # Derive the compliance status
        compliance_status = self.determine_compliance_status(
            report_status, last_report_time
        )

        # Fetch the latest report for resource-level metrics
        resource_counts = {"total": 0, "changed": 0, "failed": 0, "skipped": 0}
        corrective_changes = 0

        try:
            report = self.puppet.get_node_report(certname)
            resource_counts = self._extract_resource_counts(report)
            corrective_changes = self._extract_corrective_changes(report)
        except Exception:
            logger.warning(
                "Could not fetch latest report for %s, using defaults",
                certname,
            )

        # Fetch facts for uptime and puppet_version
        uptime_hours: float | None = None
        try:
            facts = self.puppet.get_node_facts(certname)
            uptime_hours = self._extract_uptime_hours(facts)
            puppet_version = (
                self._extract_fact(facts, "puppetversion") or puppet_version
            )
        except Exception:
            logger.warning(
                "Could not fetch facts for %s, uptime unavailable",
                certname,
            )

        return {
            "certname": certname,
            "status": compliance_status,
            "last_report_time": last_report_time,
            "last_report_status": report_status or "unknown",
            "resource_counts": resource_counts,
            "corrective_changes": corrective_changes,
            "uptime_hours": uptime_hours,
            "puppet_version": puppet_version,
            "environment": environment,
        }

    # ------------------------------------------------------------------
    # Fleet compliance
    # ------------------------------------------------------------------

    def get_fleet_compliance(self, certnames: list[str]) -> FleetCompliance:
        """Get compliance summary for a fleet of nodes.

        Iterates over every certname, calling ``get_node_compliance`` for
        each. A failure on one node is logged and skipped so it does not
        break the entire fleet report.

        Returns:
            {
                "total": int,
                "compliant": int,
                "changed": int,
                "failed": int,
                "unresponsive": int,
                "compliance_rate": float,
                "nodes": [<per-node dicts>],
            }
        """
        nodes: list[NodeCompliance] = []
        counts = {
            "compliant": 0,
            "changed": 0,
            "failed": 0,
            "unresponsive": 0,
        }

        for certname in certnames:
            try:
                node_data = self.get_node_compliance(certname)
                nodes.append(node_data)
                status = node_data.get("status", "unresponsive")
                if status in counts:
                    counts[status] += 1
                else:
                    # Treat any unknown status as unresponsive for counting
                    counts["unresponsive"] += 1
            except Exception:
                logger.error(
                    "Failed to fetch compliance for %s, marking unresponsive",
                    certname,
                    exc_info=True,
                )
                nodes.append({
                    "certname": certname,
                    "status": "unresponsive",
                    "last_report_time": None,
                    "last_report_status": "unknown",
                    "resource_counts": {
                        "total": 0,
                        "changed": 0,
                        "failed": 0,
                        "skipped": 0,
                    },
                    "corrective_changes": 0,
                    "uptime_hours": None,
                    "puppet_version": None,
                    "environment": "unknown",
                })
                counts["unresponsive"] += 1

        total = len(certnames)
        compliance_rate = (
            (counts["compliant"] / total * 100.0) if total > 0 else 0.0
        )

        return {
            "total": total,
            "compliant": counts["compliant"],
            "changed": counts["changed"],
            "failed": counts["failed"],
            "unresponsive": counts["unresponsive"],
            "compliance_rate": round(compliance_rate, 2),
            "nodes": nodes,
        }

    # ------------------------------------------------------------------
    # Drift report
    # ------------------------------------------------------------------

    def get_node_drift_report(self, certname: str, hours: int = 24) -> NodeDriftReport:
        """Get drift events for a node over a time period.

        Examines reports within the specified window and identifies runs
        where Puppet had to make corrective changes (i.e. drift was
        detected and resources were brought back into the desired state).

        Returns:
            {
                "certname": str,
                "period_hours": int,
                "total_runs": int,
                "drift_events": int,
                "resources_corrected": list[str],
            }
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        # get_node_report returns a list of reports or a single report
        # depending on implementation.  We normalise to a list.
        raw_reports = self.puppet.get_node_report(certname)
        if isinstance(raw_reports, dict):
            raw_reports = [raw_reports]

        total_runs = 0
        drift_events = 0
        resources_corrected: set[str] = set()

        for report in raw_reports:
            # Filter reports to the requested time window
            report_time_str = report.get("receive_time") or report.get(
                "start_time", ""
            )
            if not report_time_str:
                continue

            try:
                report_dt = datetime.fromisoformat(
                    report_time_str.replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                continue

            if report_dt < cutoff:
                continue

            total_runs += 1

            # A report with status "changed" indicates drift was corrected
            report_status = report.get("status", "")
            if report_status == "changed":
                drift_events += 1

                # Extract individual resource events that represent
                # corrective changes
                resource_events = report.get("resource_events", {})
                events_list = resource_events.get("data", [])
                if isinstance(events_list, list):
                    for event in events_list:
                        if event.get("status") in ("success", "changed"):
                            title = event.get("resource_title", "")
                            rtype = event.get("resource_type", "")
                            if title:
                                resources_corrected.add(
                                    f"{rtype}[{title}]" if rtype else title
                                )

                # Also handle flat "events" key used by some PuppetDB
                # response formats
                flat_events = report.get("events", [])
                if isinstance(flat_events, list):
                    for event in flat_events:
                        if event.get("status") in ("success", "changed"):
                            title = event.get("resource_title", "")
                            rtype = event.get("resource_type", "")
                            if title:
                                resources_corrected.add(
                                    f"{rtype}[{title}]" if rtype else title
                                )

        return {
            "certname": certname,
            "period_hours": hours,
            "total_runs": total_runs,
            "drift_events": drift_events,
            "resources_corrected": sorted(resources_corrected),
        }

    # ------------------------------------------------------------------
    # Static helper
    # ------------------------------------------------------------------

    @staticmethod
    def determine_compliance_status(
        report_status: str | None,
        last_report_time: str | None,
        threshold_minutes: int = 90,
    ) -> str:
        """Map Puppet report status to a compliance status string.

        Logic:
          - No report time at all -> ``"unresponsive"``
          - Report older than *threshold_minutes* -> ``"unresponsive"``
          - ``"unchanged"`` -> ``"compliant"``
          - ``"changed"`` -> ``"changed"``
          - ``"failed"`` -> ``"failed"``
          - Anything else -> ``"unknown"``
        """
        if last_report_time is None:
            return "unresponsive"

        try:
            report_dt = datetime.fromisoformat(
                last_report_time.replace("Z", "+00:00")
            )
            if datetime.now(timezone.utc) - report_dt > timedelta(
                minutes=threshold_minutes
            ):
                return "unresponsive"
        except (ValueError, TypeError):
            return "unresponsive"

        status_map = {
            "unchanged": "compliant",
            "changed": "changed",
            "failed": "failed",
        }
        return status_map.get(report_status, "unknown")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_resource_counts(report: dict[str, Any]) -> ResourceCounts:
        """Pull resource counts from a PuppetDB report dict.

        PuppetDB reports include a ``metrics`` section with a ``resources``
        group containing ``total``, ``changed``, ``failed``, ``skipped``,
        etc.  This method handles both the structured (list-of-dicts) and
        flat (dict) metric formats.
        """
        defaults = {"total": 0, "changed": 0, "failed": 0, "skipped": 0}

        metrics = report.get("metrics", {})

        # Format 1: {"resources": {"total": N, ...}}
        if isinstance(metrics, dict):
            resources_metrics = metrics.get("resources", {})
            if isinstance(resources_metrics, dict):
                return {
                    "total": resources_metrics.get("total", 0),
                    "changed": resources_metrics.get("changed", 0),
                    "failed": resources_metrics.get("failed", 0),
                    "skipped": resources_metrics.get("skipped", 0),
                }

        # Format 2: {"data": [{"category": "resources", "name": "total", "value": N}, ...]}
        if isinstance(metrics, dict) and "data" in metrics:
            metrics_list = metrics["data"]
        elif isinstance(metrics, list):
            metrics_list = metrics
        else:
            return defaults

        result = dict(defaults)
        for item in metrics_list:
            if not isinstance(item, dict):
                continue
            if item.get("category") == "resources":
                name = item.get("name", "")
                if name in result:
                    result[name] = item.get("value", 0)

        return result

    @staticmethod
    def _extract_corrective_changes(report: dict[str, Any]) -> int:
        """Count corrective changes from a PuppetDB report.

        Puppet Enterprise tracks whether a change was intentional
        (from a catalog update) or corrective (drift remediation).
        The ``corrective_change`` field on resource events indicates this.
        """
        count = 0

        # Check top-level corrective_change flag
        if report.get("corrective_change") is True:
            # If the report itself is flagged, count event-level details
            pass

        # Count individual corrective events
        resource_events = report.get("resource_events", {})
        events_list = resource_events.get("data", [])
        if isinstance(events_list, list):
            for event in events_list:
                if event.get("corrective_change") is True:
                    count += 1

        # Also handle flat "events" key
        flat_events = report.get("events", [])
        if isinstance(flat_events, list):
            for event in flat_events:
                if event.get("corrective_change") is True:
                    count += 1

        # If no event-level data but the report is flagged corrective,
        # count as at least 1
        if count == 0 and report.get("corrective_change") is True:
            count = 1

        return count

    @staticmethod
    def _extract_uptime_hours(facts: Any) -> float | None:
        """Extract system uptime in hours from a PuppetDB facts response.

        Looks for the ``system_uptime`` structured fact, falling back to
        ``uptime_seconds`` if available.
        """
        if isinstance(facts, dict):
            # Structured fact: system_uptime.seconds
            system_uptime = facts.get("system_uptime", {})
            if isinstance(system_uptime, dict):
                seconds = system_uptime.get("seconds")
                if seconds is not None:
                    return round(float(seconds) / 3600.0, 2)

            # Flat fact: uptime_seconds
            uptime_seconds = facts.get("uptime_seconds")
            if uptime_seconds is not None:
                return round(float(uptime_seconds) / 3600.0, 2)

        # facts may come back as a list of {name, value} dicts
        if isinstance(facts, list):
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                name = fact.get("name", "")
                if name == "uptime_seconds":
                    value = fact.get("value")
                    if value is not None:
                        return round(float(value) / 3600.0, 2)
                if name == "system_uptime":
                    value = fact.get("value", {})
                    if isinstance(value, dict):
                        seconds = value.get("seconds")
                        if seconds is not None:
                            return round(float(seconds) / 3600.0, 2)

        return None

    @staticmethod
    def _extract_fact(facts: Any, fact_name: str) -> str | None:
        """Extract a single fact value by name.

        Supports both dict-style facts (``{name: value}``) and
        list-of-dicts PuppetDB format (``[{name, value}, ...]``).
        """
        if isinstance(facts, dict):
            value = facts.get(fact_name)
            if value is not None:
                return str(value)

        if isinstance(facts, list):
            for fact in facts:
                if isinstance(fact, dict) and fact.get("name") == fact_name:
                    value = fact.get("value")
                    if value is not None:
                        return str(value)

        return None
