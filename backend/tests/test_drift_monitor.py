"""Unit tests for DriftMonitor and AsyncDriftMonitor in drift_monitor.py.

Covers:
- _safe_str helper
- _get_report_events
- poll_drift_events (mocked PuppetDB + DB)
- _store_events (mocked DB)
- check_drift_patterns (mocked DB)
- generate_alerts (mocked DB)
- send_drift_notifications (mocked notification services)
- AsyncDriftMonitor query methods (mocked AsyncSession)
- _map_severity_to_notification helper
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.drift_monitor import (
    AsyncDriftMonitor,
    DriftMonitor,
    _map_severity_to_notification,
)

# ---------------------------------------------------------------------------
# _map_severity_to_notification
# ---------------------------------------------------------------------------


class TestMapSeverityToNotification:
    def test_critical_maps_to_error(self):
        assert _map_severity_to_notification("critical") == "error"

    def test_high_maps_to_warning(self):
        assert _map_severity_to_notification("high") == "warning"

    def test_medium_maps_to_info(self):
        assert _map_severity_to_notification("medium") == "info"

    def test_low_maps_to_info(self):
        assert _map_severity_to_notification("low") == "info"

    def test_unknown_defaults_to_info(self):
        assert _map_severity_to_notification("banana") == "info"


# ---------------------------------------------------------------------------
# DriftMonitor._safe_str
# ---------------------------------------------------------------------------


class TestDriftMonitorSafeStr:
    def test_none_returns_none(self):
        assert DriftMonitor._safe_str(None) is None

    def test_string_returned_as_is(self):
        assert DriftMonitor._safe_str("hello") == "hello"

    def test_int_converted_to_string(self):
        assert DriftMonitor._safe_str(42) == "42"

    def test_dict_serialized_as_json(self):
        result = DriftMonitor._safe_str({"key": "value"})
        assert result == json.dumps({"key": "value"})

    def test_list_serialized_as_json(self):
        result = DriftMonitor._safe_str([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_nested_dict_serialized(self):
        data = {"a": {"b": 1}}
        result = DriftMonitor._safe_str(data)
        assert json.loads(result) == data

    def test_bool_converted_to_string(self):
        assert DriftMonitor._safe_str(True) == "True"


# ---------------------------------------------------------------------------
# DriftMonitor._get_report_events
# ---------------------------------------------------------------------------


class TestDriftMonitorGetReportEvents:
    def _make_puppet(self, events=None, raises=None):
        puppet = MagicMock()
        puppet._puppetdb_url.return_value = "https://puppet.test:8081/pdb/query/v4/events"
        if raises:
            puppet._post.side_effect = raises
        else:
            resp = MagicMock()
            resp.json.return_value = events or []
            puppet._post.return_value = resp
        return puppet

    def test_empty_hash_returns_empty_list(self):
        monitor = DriftMonitor()
        puppet = self._make_puppet()
        result = monitor._get_report_events(puppet, "")
        assert result == []
        puppet._post.assert_not_called()

    def test_filters_to_success_and_failure(self):
        events = [
            {"status": "success", "resource_type": "File", "resource_title": "/etc/hosts"},
            {"status": "noop", "resource_type": "Service", "resource_title": "httpd"},
            {"status": "failure", "resource_type": "Package", "resource_title": "openssl"},
            {"status": "skipped", "resource_type": "Exec", "resource_title": "/usr/bin/update"},
        ]
        puppet = self._make_puppet(events=events)
        monitor = DriftMonitor()
        result = monitor._get_report_events(puppet, "abc123")

        assert len(result) == 2
        statuses = {e["status"] for e in result}
        assert statuses == {"success", "failure"}

    def test_returns_empty_list_on_error(self):
        puppet = self._make_puppet(raises=RuntimeError("connection failed"))
        monitor = DriftMonitor()
        result = monitor._get_report_events(puppet, "hash123")
        assert result == []

    def test_passes_correct_query(self):
        puppet = self._make_puppet(events=[])
        monitor = DriftMonitor()
        monitor._get_report_events(puppet, "myhash")
        puppet._post.assert_called_once()
        call_args = puppet._post.call_args
        body = call_args[1]["json_body"]
        assert body == {"query": ["=", "report", "myhash"]}


# ---------------------------------------------------------------------------
# DriftMonitor._store_events
# ---------------------------------------------------------------------------


class TestDriftMonitorStoreEvents:
    def test_empty_events_returns_empty(self):
        monitor = DriftMonitor()
        result = monitor._store_events([])
        assert result == []

    def test_events_stored_and_returned(self):
        events = [
            {
                "report_hash": "hash1",
                "resource_title": "/etc/hosts",
                "property_name": "content",
                "server_request_id": str(uuid4()),
                "certname": "n1.example.com",
                "detected_at": datetime.now(timezone.utc),
                "resource_type": "File",
                "old_value": "old",
                "new_value": "new",
                "severity": "medium",
                "is_corrective": False,
                "is_resolved": False,
                "resolution_type": None,
                "resolved_at": None,
                "drift_category": "file",
                "cis_control_id": None,
                "server_name": "web01",
            }
        ]

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        # Simulate no existing duplicates
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with patch("app.services.db.get_sync_db", return_value=mock_session):
            monitor = DriftMonitor()
            stored = monitor._store_events(events)

        assert len(stored) == 1
        assert stored[0]["certname"] == "n1.example.com"
        assert stored[0]["resource_title"] == "/etc/hosts"
        assert stored[0]["severity"] == "medium"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    def test_duplicate_events_skipped(self):
        """Events that already exist (by report_hash + resource_title + property) are skipped."""
        event = {
            "report_hash": "dup-hash",
            "resource_title": "/etc/hosts",
            "property_name": "content",
            "server_request_id": str(uuid4()),
            "certname": "n1.example.com",
            "detected_at": datetime.now(timezone.utc),
            "resource_type": "File",
            "old_value": None,
            "new_value": None,
            "severity": "medium",
            "is_corrective": False,
            "is_resolved": False,
            "resolution_type": None,
            "resolved_at": None,
            "drift_category": "file",
            "cis_control_id": None,
            "server_name": "web01",
        }

        # Simulate existing duplicate row
        existing_row = MagicMock()
        existing_row.report_hash = "dup-hash"
        existing_row.resource_title = "/etc/hosts"
        existing_row.property_name = "content"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([existing_row]))
        mock_session.execute.return_value = mock_result

        with patch("app.services.db.get_sync_db", return_value=mock_session):
            monitor = DriftMonitor()
            stored = monitor._store_events([event])

        assert stored == []
        mock_session.add.assert_not_called()


# ---------------------------------------------------------------------------
# DriftMonitor.poll_drift_events
# ---------------------------------------------------------------------------


class TestDriftMonitorPollDriftEvents:
    def _make_puppet(self, reports=None, events=None):
        puppet = MagicMock()
        puppet._puppetdb_url.return_value = "https://puppet:8081/pdb/query/v4/reports"

        reports_resp = MagicMock()
        reports_resp.json.return_value = reports or []

        events_resp = MagicMock()
        events_resp.json.return_value = events or []

        puppet._post.side_effect = [reports_resp, events_resp]
        return puppet

    def test_returns_empty_on_no_reports(self):
        puppet = self._make_puppet(reports=[])
        monitor = DriftMonitor(puppet_service=puppet)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with patch("app.services.db.get_sync_db", return_value=mock_session):
            result = monitor.poll_drift_events(since_minutes=10)

        assert result == []

    def test_returns_empty_on_puppetdb_error(self):
        puppet = MagicMock()
        puppet._puppetdb_url.return_value = "https://puppet:8081/pdb/query/v4/reports"
        puppet._post.side_effect = RuntimeError("PuppetDB down")
        monitor = DriftMonitor(puppet_service=puppet)
        result = monitor.poll_drift_events(since_minutes=10)
        assert result == []

    def test_skips_unmanaged_nodes(self):
        """Reports for certnames not in the server database are skipped."""
        reports = [{
            "certname": "unmanaged.example.com",
            "hash": "h1",
            "receive_time": "2024-01-01T00:00:00Z",
        }]
        puppet = self._make_puppet(reports=reports)
        monitor = DriftMonitor(puppet_service=puppet)

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        # No rows returned = no managed servers
        mock_result = MagicMock()
        mock_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.return_value = mock_result

        with patch("app.services.db.get_sync_db", return_value=mock_session):
            result = monitor.poll_drift_events(since_minutes=10)

        assert result == []

    def test_processes_managed_node_events(self):
        """A managed node with changed events produces stored drift events."""
        server_id = str(uuid4())
        reports = [{
            "certname": "managed.example.com",
            "hash": "h1",
            "receive_time": datetime.now(timezone.utc).isoformat(),
        }]
        events = [{
            "status": "success",
            "resource_type": "File",
            "resource_title": "/etc/hosts",
            "property": "content",
            "old_value": "old",
            "new_value": "new",
            "corrective_change": True,
        }]

        puppet = MagicMock()
        puppet._puppetdb_url.return_value = "https://puppet:8081/pdb/query/v4/reports"

        reports_resp = MagicMock()
        reports_resp.json.return_value = reports

        events_resp = MagicMock()
        events_resp.json.return_value = events

        puppet._post.side_effect = [reports_resp, events_resp]

        monitor = DriftMonitor(puppet_service=puppet)

        # DB session: first execute returns managed server row
        server_row = MagicMock()
        server_row.id = UUID(server_id)
        server_row.puppet_certname = "managed.example.com"
        server_row.server_name = "web01"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        # First execute: server lookup; second execute: dup check
        server_result = MagicMock()
        server_result.__iter__ = MagicMock(return_value=iter([server_row]))
        dup_result = MagicMock()
        dup_result.__iter__ = MagicMock(return_value=iter([]))
        mock_session.execute.side_effect = [server_result, dup_result]

        with patch("app.services.db.get_sync_db", return_value=mock_session):
            result = monitor.poll_drift_events(since_minutes=10)

        assert len(result) == 1
        assert result[0]["certname"] == "managed.example.com"
        assert result[0]["resource_title"] == "/etc/hosts"
        assert result[0]["is_corrective"] is True


# ---------------------------------------------------------------------------
# DriftMonitor.check_drift_patterns
# ---------------------------------------------------------------------------


class TestDriftMonitorCheckDriftPatterns:
    def _make_session(self, repeat_rows=None, recent_count=0, unresolved_count=0):
        """Build a mock sync DB session returning expected query results."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)

        # Pattern 1: repeated drift
        repeat_result = MagicMock()
        repeat_result.__iter__ = MagicMock(return_value=iter(repeat_rows or []))

        # Pattern 2: simultaneous drift count
        simultaneous_result = MagicMock()
        simultaneous_result.scalar.return_value = recent_count

        # Pattern 3: unresolved drift count
        unresolved_result = MagicMock()
        unresolved_result.scalar.return_value = unresolved_count

        session.execute.side_effect = [repeat_result, simultaneous_result, unresolved_result]
        return session

    def test_no_patterns_returns_empty(self):
        session = self._make_session()
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")
        assert result == []

    def test_repeated_drift_pattern_detected(self):
        row = MagicMock()
        row.resource_type = "File"
        row.resource_title = "/etc/sshd_config"
        row.property_name = "content"
        row.count = 5

        session = self._make_session(repeat_rows=[row])
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")

        assert len(result) == 1
        assert result[0]["pattern_type"] == "repeated_drift"
        assert result[0]["severity"] == "high"
        assert "5" in result[0]["message"]

    def test_simultaneous_drift_critical_at_5_or_more(self):
        session = self._make_session(recent_count=5)
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")

        simultaneous = [p for p in result if p["pattern_type"] == "simultaneous_drift"]
        assert len(simultaneous) == 1
        assert simultaneous[0]["severity"] == "critical"

    def test_simultaneous_drift_not_triggered_below_5(self):
        session = self._make_session(recent_count=4)
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")

        simultaneous = [p for p in result if p["pattern_type"] == "simultaneous_drift"]
        assert simultaneous == []

    def test_compliance_drop_critical_at_10_or_more(self):
        session = self._make_session(unresolved_count=10)
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")

        compliance = [p for p in result if p["pattern_type"] == "compliance_drop"]
        assert len(compliance) == 1
        assert compliance[0]["severity"] == "critical"

    def test_compliance_drop_high_at_5_to_9(self):
        session = self._make_session(unresolved_count=7)
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")

        compliance = [p for p in result if p["pattern_type"] == "compliance_drop"]
        assert len(compliance) == 1
        assert compliance[0]["severity"] == "high"

    def test_compliance_drop_not_triggered_below_5(self):
        session = self._make_session(unresolved_count=4)
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")

        compliance = [p for p in result if p["pattern_type"] == "compliance_drop"]
        assert compliance == []

    def test_multiple_patterns_detected_together(self):
        row = MagicMock()
        row.resource_type = "Service"
        row.resource_title = "httpd"
        row.property_name = "ensure"
        row.count = 4

        session = self._make_session(repeat_rows=[row], recent_count=6, unresolved_count=12)
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            result = monitor.check_drift_patterns("server-id-1")

        pattern_types = {p["pattern_type"] for p in result}
        assert "repeated_drift" in pattern_types
        assert "simultaneous_drift" in pattern_types
        assert "compliance_drop" in pattern_types


# ---------------------------------------------------------------------------
# DriftMonitor.generate_alerts
# ---------------------------------------------------------------------------


class TestDriftMonitorGenerateAlerts:
    def _make_session(self, existing_alert_id=None):
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)

        existing = MagicMock()
        existing.scalar_one_or_none.return_value = existing_alert_id
        session.execute.return_value = existing
        return session

    def test_critical_event_generates_alert(self):
        events = [{
            "id": str(uuid4()),
            "certname": "node1",
            "server_name": "web01",
            "resource_type": "File",
            "resource_title": "/etc/sshd_config",
            "drift_category": "security",
            "severity": "critical",
            "is_corrective": True,
        }]
        session = self._make_session()
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            alerts = monitor.generate_alerts(events, patterns=[])

        assert len(alerts) == 1
        assert alerts[0]["severity"] == "critical"
        assert alerts[0]["alert_type"] == "drift_detected"
        session.add.assert_called_once()

    def test_high_event_generates_alert(self):
        events = [{
            "id": str(uuid4()),
            "certname": "node1",
            "server_name": "web01",
            "resource_type": "Service",
            "resource_title": "sshd",
            "drift_category": "service",
            "severity": "high",
            "is_corrective": False,
        }]
        session = self._make_session()
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            alerts = monitor.generate_alerts(events, patterns=[])

        assert len(alerts) == 1
        assert alerts[0]["severity"] == "high"

    def test_medium_event_does_not_generate_alert(self):
        events = [{
            "id": str(uuid4()),
            "certname": "node1",
            "server_name": "web01",
            "resource_type": "Package",
            "resource_title": "nginx",
            "drift_category": "package",
            "severity": "medium",
            "is_corrective": False,
        }]
        session = self._make_session()
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            alerts = monitor.generate_alerts(events, patterns=[])

        assert alerts == []

    def test_pattern_generates_alert(self):
        pattern = {
            "pattern_type": "simultaneous_drift",
            "severity": "critical",
            "title": "Multiple simultaneous drifts detected",
            "message": "5 drift events in the last hour.",
            "details": {"count": 5, "period_hours": 1},
        }
        session = self._make_session(existing_alert_id=None)
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            alerts = monitor.generate_alerts(events=[], patterns=[pattern])

        assert len(alerts) == 1
        assert alerts[0]["alert_type"] == "simultaneous_drift"

    def test_duplicate_pattern_alert_skipped(self):
        """If an unacknowledged alert of the same type + title exists, skip creation."""
        pattern = {
            "pattern_type": "compliance_drop",
            "severity": "high",
            "title": "Compliance warning: growing unresolved drift",
            "message": "5 unresolved events.",
            "details": {},
        }
        # Simulate existing unacknowledged alert
        session = self._make_session(existing_alert_id=str(uuid4()))
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            alerts = monitor.generate_alerts(events=[], patterns=[pattern])

        assert alerts == []

    def test_flush_called(self):
        session = self._make_session()
        with patch("app.services.db.get_sync_db", return_value=session):
            monitor = DriftMonitor()
            monitor.generate_alerts(events=[], patterns=[])

        session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# DriftMonitor.send_drift_notifications
# ---------------------------------------------------------------------------


class TestDriftMonitorSendDriftNotifications:
    def test_sends_in_app_notification_for_each_alert(self):
        alerts = [
            {"id": str(uuid4()), "alert_type": "drift_detected", "severity": "critical",
             "title": "Drift on web01", "message": "critical drift"},
        ]

        with patch("app.services.notifications.NotificationService") as mock_notif_cls:
            with patch("app.services.slack.get_slack_notifier") as mock_slack_cls:
                mock_slack = MagicMock()
                mock_slack_cls.return_value = mock_slack

                monitor = DriftMonitor()
                monitor.send_drift_notifications(events=[], alerts=alerts)

            mock_notif_cls.create_sync.assert_called_once()
            call_kwargs = mock_notif_cls.create_sync.call_args[1]
            assert call_kwargs["severity"] == "error"  # critical -> error
            assert call_kwargs["category"] == "compliance"

    def test_slack_sent_for_critical_and_high(self):
        alerts = [
            {"id": "a1", "alert_type": "drift_detected", "severity": "critical",
             "title": "Critical drift", "message": "critical"},
            {"id": "a2", "alert_type": "drift_detected", "severity": "high",
             "title": "High drift", "message": "high"},
            {"id": "a3", "alert_type": "drift_detected", "severity": "medium",
             "title": "Medium drift", "message": "medium"},
        ]

        with patch("app.services.notifications.NotificationService"):
            with patch("app.services.slack.get_slack_notifier") as mock_slack_cls:
                mock_slack = MagicMock()
                mock_slack_cls.return_value = mock_slack

                monitor = DriftMonitor()
                monitor.send_drift_notifications(events=[], alerts=alerts)

                # Only critical and high get Slack messages
                assert mock_slack.send_message.call_count == 2

    def test_notification_failures_do_not_propagate(self):
        """Failures in notification services are swallowed (best-effort)."""
        alerts = [
            {"id": "a1", "alert_type": "drift_detected", "severity": "critical",
             "title": "Crit", "message": "crit"},
        ]

        with patch("app.services.notifications.NotificationService") as mock_notif_cls:
            mock_notif_cls.create_sync.side_effect = RuntimeError("notification service down")

            with patch("app.services.slack.get_slack_notifier") as mock_slack_cls:
                mock_slack = MagicMock()
                mock_slack.send_message.side_effect = RuntimeError("slack down")
                mock_slack_cls.return_value = mock_slack

                monitor = DriftMonitor()
                # Should not raise
                monitor.send_drift_notifications(events=[], alerts=alerts)

    def test_empty_alerts_no_notifications_sent(self):
        with patch("app.services.notifications.NotificationService") as mock_notif_cls:
            with patch("app.services.slack.get_slack_notifier"):
                monitor = DriftMonitor()
                monitor.send_drift_notifications(events=[], alerts=[])

                mock_notif_cls.create_sync.assert_not_called()


# ---------------------------------------------------------------------------
# AsyncDriftMonitor.get_drift_summary
# ---------------------------------------------------------------------------


def _make_iter_result(rows):
    """Build a MagicMock execute-result that is iterable (for severity/category queries)."""
    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter(rows))
    return result


class TestAsyncDriftMonitorGetDriftSummary:
    def _make_db(self, counts: dict | None = None):
        """Build a mock AsyncSession that returns preset scalar counts."""
        counts = counts or {}

        def _s(key):
            r = MagicMock()
            r.scalar.return_value = counts.get(key, 0)
            return r

        db = AsyncMock()
        db.execute.side_effect = [
            _s("total_events"),
            _s("unresolved_events"),
            _s("auto_corrected"),
            _s("active_alerts"),
            _s("affected_servers"),
            _make_iter_result([]),   # by_severity
            _make_iter_result([]),   # by_category
        ]
        return db

    @pytest.mark.asyncio
    async def test_summary_returns_expected_keys(self):
        db = self._make_db()
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_summary()

        expected_keys = {
            "total_events", "unresolved_events", "resolved_events",
            "auto_corrected", "active_alerts", "affected_servers",
            "by_severity", "by_category", "generated_at",
        }
        assert set(result.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_summary_resolved_is_total_minus_unresolved(self):
        db = self._make_db({"total_events": 10, "unresolved_events": 3})
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_summary()

        assert result["resolved_events"] == 7

    @pytest.mark.asyncio
    async def test_summary_zero_when_no_events(self):
        db = self._make_db()
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_summary()

        assert result["total_events"] == 0
        assert result["affected_servers"] == 0
        assert result["active_alerts"] == 0


def _make_scalar_result(value):
    """Build a MagicMock execute-result that returns a scalar value synchronously."""
    result = MagicMock()
    result.scalar.return_value = value
    return result


def _make_scalars_result(rows):
    """Build a MagicMock execute-result whose .scalars().all() returns rows."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _make_scalar_one_or_none_result(value):
    """Build a MagicMock execute-result whose .scalar_one_or_none() returns value."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_async_db(*execute_return_values):
    """
    Build an AsyncMock db session where db.execute() returns each value in turn.

    Each value in execute_return_values should be a MagicMock (not AsyncMock),
    since the service code calls result.scalar() / result.scalars().all() etc.
    synchronously on the returned object.
    """
    db = AsyncMock()
    db.execute.side_effect = execute_return_values
    return db


# ---------------------------------------------------------------------------
# AsyncDriftMonitor.get_drift_events
# ---------------------------------------------------------------------------


class TestAsyncDriftMonitorGetDriftEvents:
    @pytest.mark.asyncio
    async def test_returns_pagination_structure(self):
        db = _make_async_db(
            _make_scalar_result(0),          # count query
            _make_scalars_result([]),         # events query
        )
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_events(page=1, page_size=25)

        assert result["total"] == 0
        assert result["events"] == []
        assert result["page"] == 1
        assert result["page_size"] == 25

    @pytest.mark.asyncio
    async def test_filters_applied_when_provided(self):
        db = _make_async_db(
            _make_scalar_result(5),
            _make_scalars_result([]),
        )
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_events(
            server_id="srv-123",
            severity="critical",
            category="security",
            is_resolved=False,
        )
        assert result["total"] == 5
        assert db.execute.call_count == 2


# ---------------------------------------------------------------------------
# AsyncDriftMonitor.get_drift_event_by_id
# ---------------------------------------------------------------------------


class TestAsyncDriftMonitorGetDriftEventById:
    @pytest.mark.asyncio
    async def test_returns_event_when_found(self):
        mock_event = MagicMock()
        db = _make_async_db(_make_scalar_one_or_none_result(mock_event))
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_event_by_id("event-id-1")
        assert result is mock_event

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        db = _make_async_db(_make_scalar_one_or_none_result(None))
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_event_by_id("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# AsyncDriftMonitor.acknowledge_alert
# ---------------------------------------------------------------------------


class TestAsyncDriftMonitorAcknowledgeAlert:
    @pytest.mark.asyncio
    async def test_acknowledges_existing_alert(self):
        mock_alert = MagicMock()
        mock_alert.is_acknowledged = False
        db = _make_async_db(_make_scalar_one_or_none_result(mock_alert))

        monitor = AsyncDriftMonitor(db)
        result = await monitor.acknowledge_alert("alert-id-1", "admin@example.com")

        assert result is mock_alert
        assert mock_alert.is_acknowledged is True
        assert mock_alert.acknowledged_by == "admin@example.com"
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_alert_not_found(self):
        db = _make_async_db(_make_scalar_one_or_none_result(None))
        monitor = AsyncDriftMonitor(db)
        result = await monitor.acknowledge_alert("missing-id", "admin@example.com")
        assert result is None
        db.flush.assert_not_called()


# ---------------------------------------------------------------------------
# AsyncDriftMonitor.get_drift_alerts
# ---------------------------------------------------------------------------


class TestAsyncDriftMonitorGetDriftAlerts:
    @pytest.mark.asyncio
    async def test_returns_pagination_structure(self):
        db = _make_async_db(
            _make_scalar_result(2),
            _make_scalars_result([]),
        )
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_alerts(page=1, page_size=10)

        assert result["total"] == 2
        assert result["page"] == 1
        assert result["page_size"] == 10

    @pytest.mark.asyncio
    async def test_filters_by_acknowledged_and_severity(self):
        db = _make_async_db(
            _make_scalar_result(0),
            _make_scalars_result([]),
        )
        monitor = AsyncDriftMonitor(db)
        await monitor.get_drift_alerts(is_acknowledged=False, severity="critical")
        assert db.execute.call_count == 2


# ---------------------------------------------------------------------------
# AsyncDriftMonitor.get_server_drift_timeline
# ---------------------------------------------------------------------------


class TestAsyncDriftMonitorGetServerDriftTimeline:
    @pytest.mark.asyncio
    async def test_returns_timeline_structure(self):
        db = _make_async_db(
            _make_scalar_one_or_none_result("web01.example.com"),
            _make_scalars_result([]),
        )
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_server_drift_timeline("srv-1", hours=168)

        assert result["server_request_id"] == "srv-1"
        assert result["certname"] == "web01.example.com"
        assert result["period_hours"] == 168
        assert result["events"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_certname_defaults_to_empty_string_when_none(self):
        db = _make_async_db(
            _make_scalar_one_or_none_result(None),
            _make_scalars_result([]),
        )
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_server_drift_timeline("srv-1")
        assert result["certname"] == ""


# ---------------------------------------------------------------------------
# AsyncDriftMonitor.get_drift_trends
# ---------------------------------------------------------------------------


class TestAsyncDriftMonitorGetDriftTrends:
    @pytest.mark.asyncio
    async def test_returns_trend_structure(self):
        db = _make_async_db(_make_scalars_result([]))
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_trends(days=7)

        assert result["period_days"] == 7
        assert "daily" in result
        assert "generated_at" in result
        # 7 days = 8 entries (cutoff day through today inclusive)
        assert len(result["daily"]) == 8

    @pytest.mark.asyncio
    async def test_daily_entries_have_expected_keys(self):
        db = _make_async_db(_make_scalars_result([]))
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_trends(days=3)

        for day in result["daily"]:
            assert "date" in day
            assert "total" in day
            assert "security" in day
            assert "configuration" in day
            assert "package" in day
            assert "service" in day
            assert "file" in day

    @pytest.mark.asyncio
    async def test_events_bucketed_by_day(self):
        now = datetime.now(timezone.utc)
        today = now.replace(hour=12, minute=0, second=0, microsecond=0)

        mock_event = MagicMock()
        mock_event.detected_at = today
        mock_event.drift_category = "security"

        db = _make_async_db(_make_scalars_result([mock_event]))
        monitor = AsyncDriftMonitor(db)
        result = await monitor.get_drift_trends(days=1)

        today_str = today.strftime("%Y-%m-%d")
        today_entry = next((d for d in result["daily"] if d["date"] == today_str), None)
        assert today_entry is not None
        assert today_entry["security"] == 1
        assert today_entry["total"] == 1
