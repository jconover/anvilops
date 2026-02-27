"""Unit tests for PuppetComplianceService in puppet_reports.py.

All tests use pure in-memory data and mock the PuppetEnterpriseServiceSync
dependency -- no database or network connections required.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.puppet_reports import PuppetComplianceService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_puppet_svc(
    *,
    node_status: dict | None = None,
    node_report=None,
    node_facts=None,
    report_raises: Exception | None = None,
    facts_raises: Exception | None = None,
) -> MagicMock:
    """Build a mock PuppetEnterpriseServiceSync for use in PuppetComplianceService."""
    svc = MagicMock()
    svc.get_node_status.return_value = node_status or {}
    if report_raises:
        svc.get_node_report.side_effect = report_raises
    else:
        svc.get_node_report.return_value = node_report if node_report is not None else {}
    if facts_raises:
        svc.get_node_facts.side_effect = facts_raises
    else:
        svc.get_node_facts.return_value = node_facts if node_facts is not None else {}
    return svc


def _recent_timestamp(minutes_ago: int = 5) -> str:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return dt.isoformat()


def _old_timestamp(hours_ago: int = 3) -> str:
    dt = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# determine_compliance_status (static method)
# ---------------------------------------------------------------------------


class TestDetermineComplianceStatus:
    def test_none_report_time_is_unresponsive(self):
        result = PuppetComplianceService.determine_compliance_status("unchanged", None)
        assert result == "unresponsive"

    def test_old_report_is_unresponsive(self):
        old = _old_timestamp(hours_ago=3)
        result = PuppetComplianceService.determine_compliance_status("unchanged", old)
        assert result == "unresponsive"

    def test_recent_unchanged_is_compliant(self):
        recent = _recent_timestamp(minutes_ago=5)
        result = PuppetComplianceService.determine_compliance_status("unchanged", recent)
        assert result == "compliant"

    def test_recent_changed_is_changed(self):
        recent = _recent_timestamp(minutes_ago=5)
        result = PuppetComplianceService.determine_compliance_status("changed", recent)
        assert result == "changed"

    def test_recent_failed_is_failed(self):
        recent = _recent_timestamp(minutes_ago=5)
        result = PuppetComplianceService.determine_compliance_status("failed", recent)
        assert result == "failed"

    def test_unknown_status_is_unknown(self):
        recent = _recent_timestamp(minutes_ago=5)
        result = PuppetComplianceService.determine_compliance_status("noop", recent)
        assert result == "unknown"

    def test_invalid_timestamp_is_unresponsive(self):
        result = PuppetComplianceService.determine_compliance_status("unchanged", "not-a-date")
        assert result == "unresponsive"

    def test_custom_threshold(self):
        """A timestamp 10 minutes ago should be unresponsive at threshold=5."""
        ts = _recent_timestamp(minutes_ago=10)
        result = PuppetComplianceService.determine_compliance_status(
            "unchanged", ts, threshold_minutes=5
        )
        assert result == "unresponsive"

    def test_exactly_within_threshold_is_compliant(self):
        """A timestamp 4 minutes ago should be compliant at threshold=5."""
        ts = _recent_timestamp(minutes_ago=4)
        result = PuppetComplianceService.determine_compliance_status(
            "unchanged", ts, threshold_minutes=5
        )
        assert result == "compliant"


# ---------------------------------------------------------------------------
# _extract_resource_counts (static method)
# ---------------------------------------------------------------------------


class TestExtractResourceCounts:
    def test_flat_dict_format(self):
        report = {
            "metrics": {
                "resources": {"total": 100, "changed": 5, "failed": 1, "skipped": 2}
            }
        }
        result = PuppetComplianceService._extract_resource_counts(report)
        assert result == {"total": 100, "changed": 5, "failed": 1, "skipped": 2}

    def test_list_of_dicts_format(self):
        report = {
            "metrics": [
                {"category": "resources", "name": "total", "value": 80},
                {"category": "resources", "name": "changed", "value": 3},
                {"category": "resources", "name": "failed", "value": 0},
                {"category": "resources", "name": "skipped", "value": 1},
                {"category": "time", "name": "catalog", "value": 1.5},  # ignored
            ]
        }
        result = PuppetComplianceService._extract_resource_counts(report)
        assert result["total"] == 80
        assert result["changed"] == 3
        assert result["failed"] == 0
        assert result["skipped"] == 1

    def test_plain_list_format(self):
        # When metrics is a plain list (not wrapped in a dict), the code
        # takes the elif isinstance(metrics, list) branch.
        report = {
            "metrics": [
                {"category": "resources", "name": "total", "value": 50},
                {"category": "resources", "name": "changed", "value": 2},
                {"category": "resources", "name": "failed", "value": 0},
                {"category": "resources", "name": "skipped", "value": 0},
                {"category": "time", "name": "catalog", "value": 1.5},  # ignored
            ]
        }
        result = PuppetComplianceService._extract_resource_counts(report)
        assert result["total"] == 50
        assert result["changed"] == 2
        assert result["failed"] == 0
        assert result["skipped"] == 0

    def test_empty_metrics_returns_defaults(self):
        result = PuppetComplianceService._extract_resource_counts({})
        assert result == {"total": 0, "changed": 0, "failed": 0, "skipped": 0}

    def test_missing_keys_default_to_zero(self):
        report = {"metrics": {"resources": {"total": 10}}}
        result = PuppetComplianceService._extract_resource_counts(report)
        assert result["total"] == 10
        assert result["changed"] == 0
        assert result["failed"] == 0
        assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# _extract_corrective_changes (static method)
# ---------------------------------------------------------------------------


class TestExtractCorrectiveChanges:
    def test_counts_event_level_corrective(self):
        report = {
            "resource_events": {
                "data": [
                    {"corrective_change": True, "resource_title": "sshd"},
                    {"corrective_change": False, "resource_title": "httpd"},
                    {"corrective_change": True, "resource_title": "ntpd"},
                ]
            }
        }
        assert PuppetComplianceService._extract_corrective_changes(report) == 2

    def test_counts_flat_events(self):
        report = {
            "events": [
                {"corrective_change": True},
                {"corrective_change": True},
            ]
        }
        assert PuppetComplianceService._extract_corrective_changes(report) == 2

    def test_top_level_flag_counts_as_one_when_no_events(self):
        report = {"corrective_change": True}
        assert PuppetComplianceService._extract_corrective_changes(report) == 1

    def test_no_corrective_changes_returns_zero(self):
        assert PuppetComplianceService._extract_corrective_changes({}) == 0

    def test_top_level_false_with_no_events_returns_zero(self):
        report = {"corrective_change": False}
        assert PuppetComplianceService._extract_corrective_changes(report) == 0


# ---------------------------------------------------------------------------
# _extract_uptime_hours (static method)
# ---------------------------------------------------------------------------


class TestExtractUptimeHours:
    def test_system_uptime_dict(self):
        facts = {"system_uptime": {"seconds": 7200}}
        result = PuppetComplianceService._extract_uptime_hours(facts)
        assert result == 2.0

    def test_uptime_seconds_flat(self):
        facts = {"uptime_seconds": 3600}
        result = PuppetComplianceService._extract_uptime_hours(facts)
        assert result == 1.0

    def test_list_of_dicts_uptime_seconds(self):
        facts = [
            {"name": "uptime_seconds", "value": 5400},
            {"name": "os", "value": "Linux"},
        ]
        result = PuppetComplianceService._extract_uptime_hours(facts)
        assert result == 1.5

    def test_list_of_dicts_system_uptime(self):
        facts = [
            {"name": "system_uptime", "value": {"seconds": 3600}},
        ]
        result = PuppetComplianceService._extract_uptime_hours(facts)
        assert result == 1.0

    def test_no_uptime_returns_none(self):
        assert PuppetComplianceService._extract_uptime_hours({}) is None

    def test_none_input_returns_none(self):
        assert PuppetComplianceService._extract_uptime_hours(None) is None

    def test_rounding(self):
        facts = {"uptime_seconds": 3661}
        result = PuppetComplianceService._extract_uptime_hours(facts)
        # 3661 / 3600 = 1.0169..., rounded to 2 decimal places = 1.02
        assert result == round(3661 / 3600, 2)


# ---------------------------------------------------------------------------
# _extract_fact (static method)
# ---------------------------------------------------------------------------


class TestExtractFact:
    def test_dict_style(self):
        facts = {"puppetversion": "7.28.0", "os": "Linux"}
        assert PuppetComplianceService._extract_fact(facts, "puppetversion") == "7.28.0"

    def test_list_style(self):
        facts = [
            {"name": "puppetversion", "value": "7.28.0"},
            {"name": "os", "value": "Linux"},
        ]
        assert PuppetComplianceService._extract_fact(facts, "puppetversion") == "7.28.0"

    def test_missing_fact_returns_none(self):
        assert PuppetComplianceService._extract_fact({}, "missing") is None

    def test_list_missing_returns_none(self):
        facts = [{"name": "other", "value": "v"}]
        assert PuppetComplianceService._extract_fact(facts, "missing") is None

    def test_non_string_value_is_stringified(self):
        facts = {"some_count": 42}
        assert PuppetComplianceService._extract_fact(facts, "some_count") == "42"


# ---------------------------------------------------------------------------
# get_node_compliance
# ---------------------------------------------------------------------------


class TestGetNodeCompliance:
    def test_compliant_node_full_data(self):
        recent = _recent_timestamp(minutes_ago=5)
        puppet_mock = _make_puppet_svc(
            node_status={
                "report_timestamp": recent,
                "latest_report_status": "unchanged",
                "report_environment": "production",
            },
            node_report={
                "metrics": {"resources": {"total": 100, "changed": 0, "failed": 0, "skipped": 0}}
            },
            node_facts={"uptime_seconds": 7200, "puppetversion": "7.28.0"},
        )
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_compliance("node1.example.com")

        assert result["certname"] == "node1.example.com"
        assert result["status"] == "compliant"
        assert result["last_report_status"] == "unchanged"
        assert result["environment"] == "production"
        assert result["uptime_hours"] == 2.0
        assert result["puppet_version"] == "7.28.0"
        assert result["resource_counts"]["total"] == 100

    def test_failed_node(self):
        recent = _recent_timestamp(minutes_ago=5)
        puppet_mock = _make_puppet_svc(
            node_status={
                "report_timestamp": recent,
                "latest_report_status": "failed",
                "report_environment": "staging",
            }
        )
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_compliance("node-fail.example.com")

        assert result["status"] == "failed"
        assert result["last_report_status"] == "failed"

    def test_unresponsive_node_no_timestamp(self):
        puppet_mock = _make_puppet_svc(
            node_status={
                "latest_report_status": "unchanged",
                "report_environment": "production",
            }
        )
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_compliance("silent-node.example.com")

        assert result["status"] == "unresponsive"

    def test_report_fetch_failure_uses_defaults(self):
        """If get_node_report raises, resource_counts default to zeros."""
        recent = _recent_timestamp(minutes_ago=5)
        puppet_mock = _make_puppet_svc(
            node_status={
                "report_timestamp": recent,
                "latest_report_status": "unchanged",
                "report_environment": "production",
            },
            report_raises=RuntimeError("PuppetDB unavailable"),
        )
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_compliance("node1.example.com")

        assert result["resource_counts"] == {"total": 0, "changed": 0, "failed": 0, "skipped": 0}
        assert result["corrective_changes"] == 0

    def test_facts_fetch_failure_uses_none(self):
        """If get_node_facts raises, uptime_hours is None."""
        recent = _recent_timestamp(minutes_ago=5)
        puppet_mock = _make_puppet_svc(
            node_status={
                "report_timestamp": recent,
                "latest_report_status": "unchanged",
                "report_environment": "production",
            },
            facts_raises=RuntimeError("facts unavailable"),
        )
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_compliance("node1.example.com")

        assert result["uptime_hours"] is None

    def test_no_report_time_uses_unknown_status(self):
        puppet_mock = _make_puppet_svc(
            node_status={"report_environment": "production"}
        )
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_compliance("no-ts.example.com")

        assert result["last_report_status"] == "unknown"


# ---------------------------------------------------------------------------
# get_fleet_compliance
# ---------------------------------------------------------------------------


class TestGetFleetCompliance:
    def test_empty_fleet(self):
        puppet_mock = _make_puppet_svc()
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_fleet_compliance([])

        assert result["total"] == 0
        assert result["compliance_rate"] == 0.0
        assert result["nodes"] == []

    def test_all_compliant(self):
        recent = _recent_timestamp(minutes_ago=5)
        puppet_mock = _make_puppet_svc(
            node_status={
                "report_timestamp": recent,
                "latest_report_status": "unchanged",
                "report_environment": "production",
            }
        )
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_fleet_compliance(["n1", "n2", "n3"])

        assert result["total"] == 3
        assert result["compliant"] == 3
        assert result["compliance_rate"] == 100.0

    def test_mixed_statuses(self):
        recent = _recent_timestamp(minutes_ago=5)

        def side_effect(certname):
            statuses = {
                "compliant": "unchanged",
                "changed": "changed",
                "failed": "failed",
            }
            status = statuses.get(certname, "unchanged")
            return {
                "certname": certname,
                "status": PuppetComplianceService.determine_compliance_status(status, recent),
                "last_report_time": recent,
                "last_report_status": status,
                "resource_counts": {"total": 0, "changed": 0, "failed": 0, "skipped": 0},
                "corrective_changes": 0,
                "uptime_hours": None,
                "puppet_version": None,
                "environment": "production",
            }

        puppet_mock = _make_puppet_svc()
        svc = PuppetComplianceService(puppet_mock)
        svc.get_node_compliance = MagicMock(side_effect=side_effect)

        result = svc.get_fleet_compliance(["compliant", "changed", "failed"])
        assert result["compliant"] == 1
        assert result["changed"] == 1
        assert result["failed"] == 1
        assert round(result["compliance_rate"], 2) == round(1 / 3 * 100, 2)

    def test_node_failure_marked_unresponsive(self):
        """If get_node_compliance raises for a node, it is marked unresponsive."""
        puppet_mock = _make_puppet_svc()
        svc = PuppetComplianceService(puppet_mock)
        svc.get_node_compliance = MagicMock(
            side_effect=RuntimeError("connection refused")
        )

        result = svc.get_fleet_compliance(["failing-node"])
        assert result["total"] == 1
        assert result["unresponsive"] == 1
        assert result["nodes"][0]["status"] == "unresponsive"
        assert result["nodes"][0]["certname"] == "failing-node"

    def test_compliance_rate_calculation(self):
        recent = _recent_timestamp(minutes_ago=5)

        def side_effect(certname):
            is_compliant = certname.startswith("ok")
            return {
                "certname": certname,
                "status": "compliant" if is_compliant else "failed",
                "last_report_time": recent,
                "last_report_status": "unchanged" if is_compliant else "failed",
                "resource_counts": {"total": 0, "changed": 0, "failed": 0, "skipped": 0},
                "corrective_changes": 0,
                "uptime_hours": None,
                "puppet_version": None,
                "environment": "production",
            }

        puppet_mock = _make_puppet_svc()
        svc = PuppetComplianceService(puppet_mock)
        svc.get_node_compliance = MagicMock(side_effect=side_effect)

        # 2 compliant, 2 failed => 50%
        result = svc.get_fleet_compliance(["ok1", "ok2", "bad1", "bad2"])
        assert result["compliance_rate"] == 50.0


# ---------------------------------------------------------------------------
# get_node_drift_report
# ---------------------------------------------------------------------------


class TestGetNodeDriftReport:
    def _make_report(self, minutes_ago: int, status: str, events=None) -> dict:
        dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        report = {
            "receive_time": dt.isoformat(),
            "status": status,
        }
        if events is not None:
            report["resource_events"] = {"data": events}
        return report

    def test_no_drift_in_window(self):
        puppet_mock = _make_puppet_svc(node_report=[])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        assert result["certname"] == "n1"
        assert result["total_runs"] == 0
        assert result["drift_events"] == 0
        assert result["resources_corrected"] == []

    def test_reports_outside_window_excluded(self):
        old_report = self._make_report(minutes_ago=25 * 60, status="changed")
        puppet_mock = _make_puppet_svc(node_report=[old_report])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        # Old report is outside 24h window
        assert result["total_runs"] == 0
        assert result["drift_events"] == 0

    def test_unchanged_reports_not_drift(self):
        report = self._make_report(minutes_ago=5, status="unchanged")
        puppet_mock = _make_puppet_svc(node_report=[report])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        assert result["total_runs"] == 1
        assert result["drift_events"] == 0

    def test_changed_report_counted_as_drift(self):
        report = self._make_report(
            minutes_ago=5,
            status="changed",
            events=[
                {"status": "success", "resource_type": "File", "resource_title": "/etc/hosts"},
                {"status": "success", "resource_type": "Service", "resource_title": "httpd"},
            ],
        )
        puppet_mock = _make_puppet_svc(node_report=[report])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        assert result["total_runs"] == 1
        assert result["drift_events"] == 1
        assert "File[/etc/hosts]" in result["resources_corrected"]
        assert "Service[httpd]" in result["resources_corrected"]

    def test_resources_deduplicated_across_reports(self):
        """The same resource corrected in multiple reports appears only once."""
        report1 = self._make_report(
            minutes_ago=10,
            status="changed",
            events=[{"status": "success", "resource_type": "File", "resource_title": "/etc/hosts"}],
        )
        report2 = self._make_report(
            minutes_ago=5,
            status="changed",
            events=[{"status": "success", "resource_type": "File", "resource_title": "/etc/hosts"}],
        )
        puppet_mock = _make_puppet_svc(node_report=[report1, report2])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        assert result["drift_events"] == 2
        assert result["resources_corrected"].count("File[/etc/hosts]") == 1

    def test_dict_report_wrapped_to_list(self):
        """If get_node_report returns a single dict (not list), it is handled."""
        recent = datetime.now(timezone.utc) - timedelta(minutes=5)
        report = {
            "receive_time": recent.isoformat(),
            "status": "unchanged",
        }
        puppet_mock = _make_puppet_svc(node_report=report)
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        assert result["total_runs"] == 1

    def test_flat_events_key_is_also_parsed(self):
        """Reports using the flat 'events' key (not nested resource_events) are handled."""
        report = {
            "receive_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(),
            "status": "changed",
            "events": [
                {"status": "success", "resource_type": "Package", "resource_title": "nginx"},
            ],
        }
        puppet_mock = _make_puppet_svc(node_report=[report])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        assert result["drift_events"] == 1
        assert "Package[nginx]" in result["resources_corrected"]

    def test_invalid_receive_time_skipped(self):
        report = {
            "receive_time": "not-a-date",
            "status": "changed",
        }
        puppet_mock = _make_puppet_svc(node_report=[report])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        # Invalid timestamp -- report skipped
        assert result["total_runs"] == 0

    def test_missing_receive_time_skipped(self):
        report = {"status": "changed"}
        puppet_mock = _make_puppet_svc(node_report=[report])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        assert result["total_runs"] == 0

    def test_resources_corrected_sorted(self):
        report = self._make_report(
            minutes_ago=5,
            status="changed",
            events=[
                {"status": "success", "resource_type": "Service", "resource_title": "nginx"},
                {"status": "success", "resource_type": "File", "resource_title": "/etc/app.conf"},
            ],
        )
        puppet_mock = _make_puppet_svc(node_report=[report])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=24)

        corrected = result["resources_corrected"]
        assert corrected == sorted(corrected)

    def test_period_hours_in_result(self):
        puppet_mock = _make_puppet_svc(node_report=[])
        svc = PuppetComplianceService(puppet_mock)
        result = svc.get_node_drift_report("n1", hours=48)
        assert result["period_hours"] == 48
