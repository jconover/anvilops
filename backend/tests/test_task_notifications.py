"""Unit tests for app.tasks.notifications — Slack notification Celery tasks.

All external services are mocked.
"""

from unittest.mock import MagicMock, patch

from app.tasks.notifications import _DISPATCH_MAP, send_slack_notification

# ---------------------------------------------------------------------------
# _DISPATCH_MAP coverage
# ---------------------------------------------------------------------------


class TestDispatchMap:
    def test_all_expected_types_present(self):
        expected = {
            "build_started",
            "build_completed",
            "build_failed",
            "approval_requested",
            "approval_granted",
            "approval_rejected",
            "decommission_started",
            "decommission_completed",
        }
        assert set(_DISPATCH_MAP.keys()) == expected

    def test_values_are_method_names(self):
        for method_name in _DISPATCH_MAP.values():
            assert method_name.startswith("notify_")


# ---------------------------------------------------------------------------
# send_slack_notification task
# ---------------------------------------------------------------------------


class TestSendSlackNotification:
    """Tests call the bound task directly — Celery injects ``self``."""

    @patch("app.tasks.notifications.get_slack_notifier")
    def test_successful_send(self, mock_get_notifier):
        mock_notifier = MagicMock()
        mock_notifier.notify_build_started.return_value = True
        mock_get_notifier.return_value = mock_notifier

        result = send_slack_notification("build_started", server_name="test-01")
        assert result["status"] == "sent"
        assert result["type"] == "build_started"
        mock_notifier.notify_build_started.assert_called_once_with(
            server_name="test-01",
        )

    @patch("app.tasks.notifications.get_slack_notifier")
    def test_skipped_when_method_returns_false(self, mock_get_notifier):
        mock_notifier = MagicMock()
        mock_notifier.notify_build_completed.return_value = False
        mock_get_notifier.return_value = mock_notifier

        result = send_slack_notification("build_completed")
        assert result["status"] == "skipped"

    def test_unknown_type_returns_error(self):
        result = send_slack_notification("nonexistent_type")
        assert result["status"] == "error"
        assert "Unknown" in result["detail"]

    @patch("app.tasks.notifications.get_slack_notifier")
    def test_exception_triggers_retry(self, mock_get_notifier):
        mock_notifier = MagicMock()
        mock_notifier.notify_build_started.side_effect = ConnectionError("timeout")
        mock_get_notifier.return_value = mock_notifier

        # Mock the task's retry to simulate max retries exceeded
        with patch.object(
            send_slack_notification, "retry",
            side_effect=send_slack_notification.MaxRetriesExceededError(),
        ):
            result = send_slack_notification("build_started")
        assert result["status"] == "failed"
        assert "timeout" in result["detail"]
