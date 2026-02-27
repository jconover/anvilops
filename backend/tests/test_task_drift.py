"""Unit tests for drift task helper functions.

Tests _get_drift_monitor factory, _send_daily_digest_slack,
and _send_daily_digest_notification. All external calls are mocked.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.drift import _send_daily_digest_notification, _send_daily_digest_slack


# ---------------------------------------------------------------------------
# _send_daily_digest_slack
# ---------------------------------------------------------------------------


def _make_report(**overrides):
    base = {
        "report_date": "2024-01-15",
        "new_events": 5,
        "unresolved_total": 12,
        "auto_corrected": 3,
        "affected_servers": 2,
        "active_alerts": 1,
        "by_severity": {"critical": 0, "high": 1, "medium": 2, "low": 2},
        "by_category": {"security": 1, "configuration": 2, "package": 1, "service": 0, "file": 1},
        "top_resources": [],
    }
    base.update(overrides)
    return base


class TestSendDailyDigestSlack:
    def test_calls_notifier_send_message(self):
        mock_notifier = MagicMock()
        with patch("app.services.slack.get_slack_notifier", return_value=mock_notifier):
            _send_daily_digest_slack(_make_report())
        mock_notifier.send_message.assert_called_once()

    def test_red_color_for_critical_severity(self):
        mock_notifier = MagicMock()
        report = _make_report(by_severity={"critical": 2, "high": 0, "medium": 0, "low": 0})
        with patch("app.services.slack.get_slack_notifier", return_value=mock_notifier):
            _send_daily_digest_slack(report)
        payload = mock_notifier.send_message.call_args[0][0]
        assert payload["attachments"][0]["color"] == "#F44336"

    def test_yellow_color_for_high_severity_no_critical(self):
        mock_notifier = MagicMock()
        report = _make_report(by_severity={"critical": 0, "high": 3, "medium": 0, "low": 0})
        with patch("app.services.slack.get_slack_notifier", return_value=mock_notifier):
            _send_daily_digest_slack(report)
        payload = mock_notifier.send_message.call_args[0][0]
        assert payload["attachments"][0]["color"] == "#FFC107"

    def test_green_color_for_no_critical_or_high(self):
        mock_notifier = MagicMock()
        report = _make_report(by_severity={"critical": 0, "high": 0, "medium": 5, "low": 2})
        with patch("app.services.slack.get_slack_notifier", return_value=mock_notifier):
            _send_daily_digest_slack(report)
        payload = mock_notifier.send_message.call_args[0][0]
        assert payload["attachments"][0]["color"] == "#4CAF50"

    def test_payload_has_attachments(self):
        mock_notifier = MagicMock()
        with patch("app.services.slack.get_slack_notifier", return_value=mock_notifier):
            _send_daily_digest_slack(_make_report())
        payload = mock_notifier.send_message.call_args[0][0]
        assert "attachments" in payload
        assert len(payload["attachments"]) == 1

    def test_payload_contains_report_date(self):
        mock_notifier = MagicMock()
        report = _make_report(report_date="2024-06-01")
        with patch("app.services.slack.get_slack_notifier", return_value=mock_notifier):
            _send_daily_digest_slack(report)
        payload = mock_notifier.send_message.call_args[0][0]
        assert "2024-06-01" in payload["attachments"][0]["title"]

    def test_exception_is_swallowed(self, caplog):
        with patch(
            "app.services.slack.get_slack_notifier",
            side_effect=Exception("Slack down"),
        ):
            with caplog.at_level(logging.ERROR):
                # Should NOT raise
                _send_daily_digest_slack(_make_report())
        assert "Failed to send daily drift digest to Slack" in caplog.text

    def test_fields_include_new_events(self):
        mock_notifier = MagicMock()
        report = _make_report(new_events=42)
        with patch("app.services.slack.get_slack_notifier", return_value=mock_notifier):
            _send_daily_digest_slack(report)
        payload = mock_notifier.send_message.call_args[0][0]
        field_values = [f["value"] for f in payload["attachments"][0]["fields"]]
        assert "42" in field_values


# ---------------------------------------------------------------------------
# _send_daily_digest_notification
# ---------------------------------------------------------------------------


class TestSendDailyDigestNotification:
    def test_creates_notification_when_events_exist(self):
        mock_ns = MagicMock()
        report = _make_report(new_events=5, unresolved_total=10)
        with patch("app.services.notifications.NotificationService", mock_ns):
            _send_daily_digest_notification(report)
        mock_ns.create_sync.assert_called_once()

    def test_skips_when_no_events_and_no_unresolved(self):
        mock_ns = MagicMock()
        report = _make_report(new_events=0, unresolved_total=0)
        with patch("app.services.notifications.NotificationService", mock_ns):
            _send_daily_digest_notification(report)
        mock_ns.create_sync.assert_not_called()

    def test_creates_notification_when_unresolved_nonzero(self):
        mock_ns = MagicMock()
        report = _make_report(new_events=0, unresolved_total=3)
        with patch("app.services.notifications.NotificationService", mock_ns):
            _send_daily_digest_notification(report)
        mock_ns.create_sync.assert_called_once()

    def test_severity_error_for_critical_events(self):
        mock_ns = MagicMock()
        report = _make_report(
            new_events=1,
            unresolved_total=1,
            by_severity={"critical": 1, "high": 0, "medium": 0, "low": 0},
        )
        with patch("app.services.notifications.NotificationService", mock_ns):
            _send_daily_digest_notification(report)
        kwargs = mock_ns.create_sync.call_args[1]
        assert kwargs["severity"] == "error"

    def test_severity_warning_for_high_no_critical(self):
        mock_ns = MagicMock()
        report = _make_report(
            new_events=1,
            unresolved_total=1,
            by_severity={"critical": 0, "high": 2, "medium": 0, "low": 0},
        )
        with patch("app.services.notifications.NotificationService", mock_ns):
            _send_daily_digest_notification(report)
        kwargs = mock_ns.create_sync.call_args[1]
        assert kwargs["severity"] == "warning"

    def test_severity_info_for_low_severity(self):
        mock_ns = MagicMock()
        report = _make_report(
            new_events=1,
            unresolved_total=1,
            by_severity={"critical": 0, "high": 0, "medium": 3, "low": 1},
        )
        with patch("app.services.notifications.NotificationService", mock_ns):
            _send_daily_digest_notification(report)
        kwargs = mock_ns.create_sync.call_args[1]
        assert kwargs["severity"] == "info"

    def test_notification_category_is_compliance(self):
        mock_ns = MagicMock()
        report = _make_report(new_events=1, unresolved_total=1)
        with patch("app.services.notifications.NotificationService", mock_ns):
            _send_daily_digest_notification(report)
        kwargs = mock_ns.create_sync.call_args[1]
        assert kwargs["category"] == "compliance"

    def test_exception_is_swallowed(self, caplog):
        report = _make_report(new_events=1, unresolved_total=1)
        with patch(
            "app.services.notifications.NotificationService",
        ) as mock_ns:
            mock_ns.create_sync.side_effect = Exception("DB error")
            with caplog.at_level(logging.ERROR):
                _send_daily_digest_notification(report)
        assert "Failed to send daily drift digest notification" in caplog.text
