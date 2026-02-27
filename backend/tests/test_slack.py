"""Unit tests for the SlackNotifier service.

All outbound HTTP calls are mocked -- no real Slack webhook required.
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.slack import (
    COLOR_DECOM,
    COLOR_FAILURE,
    COLOR_INFO,
    COLOR_NEUTRAL,
    COLOR_SUCCESS,
    COLOR_WARNING,
    SlackNotifier,
    get_slack_notifier,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def notifier() -> SlackNotifier:
    return SlackNotifier(
        webhook_url="https://hooks.slack.com/services/T00/B00/XXXX",
        enabled=True,
        app_url="http://localhost:3000",
        channel="#anvilops-builds",
    )


@pytest.fixture
def disabled_notifier() -> SlackNotifier:
    return SlackNotifier(
        webhook_url="https://hooks.slack.com/services/T00/B00/XXXX",
        enabled=False,
    )


def _mock_http_response(status_code: int, text: str = "ok") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


def _capture_payload(notifier: SlackNotifier, method_call) -> dict:
    """Run method_call with a mock HTTP client and return the JSON payload sent."""
    mock_resp = _mock_http_response(200)
    with patch("httpx.Client") as mock_cls:
        mock_http = MagicMock()
        mock_http.post.return_value = mock_resp
        mock_cls.return_value.__enter__.return_value = mock_http
        method_call()
        return mock_http.post.call_args.kwargs["json"]


# ---------------------------------------------------------------------------
# send_message — core transport
# ---------------------------------------------------------------------------


class TestSendMessage:
    def test_returns_true_on_success(self, notifier: SlackNotifier):
        mock_resp = _mock_http_response(200)
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_resp
            mock_cls.return_value.__enter__.return_value = mock_http
            result = notifier.send_message({"text": "hello"})
        assert result is True

    def test_returns_false_when_disabled(self, disabled_notifier: SlackNotifier):
        result = disabled_notifier.send_message({"text": "hello"})
        assert result is False

    def test_returns_false_when_no_webhook_url(self):
        n = SlackNotifier(webhook_url="", enabled=True)
        result = n.send_message({"text": "hello"})
        assert result is False

    def test_returns_false_on_non_200(self, notifier: SlackNotifier):
        mock_resp = _mock_http_response(400, "bad_request")
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_resp
            mock_cls.return_value.__enter__.return_value = mock_http
            result = notifier.send_message({"text": "hi"})
        assert result is False

    def test_returns_false_on_timeout(self, notifier: SlackNotifier):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.side_effect = httpx.TimeoutException("timed out")
            mock_cls.return_value.__enter__.return_value = mock_http
            result = notifier.send_message({"text": "hi"})
        assert result is False

    def test_returns_false_on_http_error(self, notifier: SlackNotifier):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.side_effect = httpx.HTTPError("connection error")
            mock_cls.return_value.__enter__.return_value = mock_http
            result = notifier.send_message({"text": "hi"})
        assert result is False

    def test_returns_false_on_unexpected_exception(self, notifier: SlackNotifier):
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.side_effect = RuntimeError("unexpected")
            mock_cls.return_value.__enter__.return_value = mock_http
            result = notifier.send_message({"text": "hi"})
        assert result is False

    def test_channel_added_to_payload_when_configured(self, notifier: SlackNotifier):
        mock_resp = _mock_http_response(200)
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_resp
            mock_cls.return_value.__enter__.return_value = mock_http
            notifier.send_message({"text": "hi"})
            payload = mock_http.post.call_args.kwargs["json"]
        assert payload.get("channel") == "#anvilops-builds"

    def test_channel_not_overridden_if_already_in_payload(self, notifier: SlackNotifier):
        mock_resp = _mock_http_response(200)
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_resp
            mock_cls.return_value.__enter__.return_value = mock_http
            notifier.send_message({"text": "hi", "channel": "#other-channel"})
            payload = mock_http.post.call_args.kwargs["json"]
        # setdefault should not override an existing channel
        assert payload["channel"] == "#other-channel"


# ---------------------------------------------------------------------------
# notify_build_started
# ---------------------------------------------------------------------------


class TestNotifyBuildStarted:
    def test_returns_true_on_success(self, notifier: SlackNotifier):
        mock_resp = _mock_http_response(200)
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_resp
            mock_cls.return_value.__enter__.return_value = mock_http
            result = notifier.notify_build_started(
                "web-01", "production", "amazon_linux_2023", "medium", "req-123"
            )
        assert result is True

    def test_payload_contains_build_started_title(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_started(
                "web-01", "production", "amazon_linux_2023", "medium", "req-123"
            )

        payload = _capture_payload(notifier, call)
        attachment = payload["attachments"][0]
        assert "Build Started" in attachment["title"]

    def test_payload_attachment_color_is_info(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_started(
                "web-01", "dev", "ubuntu_2204", "small", "req-abc"
            )

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_INFO

    def test_fields_include_server_and_environment(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_started(
                "app-server-01", "staging", "rhel_9", "large", "req-xyz"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        titles = [f["title"] for f in fields]
        assert "Server" in titles
        assert "Environment" in titles


# ---------------------------------------------------------------------------
# notify_build_completed
# ---------------------------------------------------------------------------


class TestNotifyBuildCompleted:
    def test_returns_true_on_success(self, notifier: SlackNotifier):
        mock_resp = _mock_http_response(200)
        with patch("httpx.Client") as mock_cls:
            mock_http = MagicMock()
            mock_http.post.return_value = mock_resp
            mock_cls.return_value.__enter__.return_value = mock_http
            result = notifier.notify_build_completed(
                "web-01", "production", "10.0.1.50", "web-01.example.com", "req-123"
            )
        assert result is True

    def test_payload_color_is_success(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_completed(
                "web-01", "production", "10.0.1.50", None, "req-123"
            )

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_SUCCESS

    def test_optional_ip_field_included_when_present(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_completed(
                "web-01", "production", "10.0.1.50", None, "req-123"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        field_titles = [f["title"] for f in fields]
        assert "Private IP" in field_titles

    def test_optional_ip_omitted_when_none(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_completed(
                "web-01", "production", None, None, "req-123"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        field_titles = [f["title"] for f in fields]
        assert "Private IP" not in field_titles

    def test_duration_field_included_when_present(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_completed(
                "web-01", "production", None, None, "req-123", duration_seconds=125
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        field_titles = [f["title"] for f in fields]
        assert "Duration" in field_titles


# ---------------------------------------------------------------------------
# notify_build_failed
# ---------------------------------------------------------------------------


class TestNotifyBuildFailed:
    def test_payload_color_is_failure(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_failed("web-01", "prod", "Terraform error", "req-1")

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_FAILURE

    def test_error_appears_in_fields(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_failed(
                "web-01", "prod", "Timeout connecting to provider", "req-1"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        error_fields = [f for f in fields if f["title"] == "Error"]
        assert len(error_fields) == 1
        assert "Timeout" in error_fields[0]["value"]

    def test_long_error_is_truncated(self, notifier: SlackNotifier):
        long_error = "E" * 600

        def call():
            notifier.notify_build_failed("web-01", "prod", long_error, "req-1")

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        error_field = next(f for f in fields if f["title"] == "Error")
        # Should be truncated to 500 chars + "..."
        assert len(error_field["value"]) < len(long_error) + 10

    def test_step_field_included_when_provided(self, notifier: SlackNotifier):
        def call():
            notifier.notify_build_failed(
                "web-01", "prod", "Error msg", "req-1", step="terraform_apply"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        step_fields = [f for f in fields if f["title"] == "Failed Step"]
        assert len(step_fields) == 1


# ---------------------------------------------------------------------------
# notify_approval_requested
# ---------------------------------------------------------------------------


class TestNotifyApprovalRequested:
    def test_payload_color_is_warning(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_requested(
                "web-01", "production", "xl", "jdoe", "req-1"
            )

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_WARNING

    def test_approval_buttons_are_present(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_requested(
                "web-01", "production", "xl", "jdoe", "req-1"
            )

        payload = _capture_payload(notifier, call)
        attachment = payload["attachments"][0]
        action_values = [a["value"] for a in attachment["actions"] if "value" in a]
        assert any("approve:req-1" in v for v in action_values)
        assert any("reject:req-1" in v for v in action_values)

    def test_production_environment_adds_reason(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_requested(
                "web-01", "production", "small", "jdoe", "req-1"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        reason_fields = [f for f in fields if f["title"] == "Reason"]
        assert len(reason_fields) == 1
        assert "Production" in reason_fields[0]["value"]

    def test_xl_instance_adds_reason(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_requested(
                "web-01", "staging", "xl", "jdoe", "req-1"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        reason_fields = [f for f in fields if f["title"] == "Reason"]
        assert "xl" in reason_fields[0]["value"].lower()

    def test_callback_id_contains_request_id(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_requested(
                "web-01", "production", "small", "jdoe", "req-abc"
            )

        payload = _capture_payload(notifier, call)
        assert "req-abc" in payload["attachments"][0]["callback_id"]


# ---------------------------------------------------------------------------
# notify_approval_granted / rejected
# ---------------------------------------------------------------------------


class TestNotifyApprovalGrantedRejected:
    def test_granted_uses_success_color(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_granted("web-01", "alice", "req-1")

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_SUCCESS

    def test_rejected_uses_failure_color(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_rejected("web-01", "alice", "Not needed", "req-1")

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_FAILURE

    def test_rejected_reason_field_when_provided(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_rejected(
                "web-01", "alice", "Too expensive", "req-1"
            )

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        reason_fields = [f for f in fields if f["title"] == "Reason"]
        assert len(reason_fields) == 1
        assert "Too expensive" in reason_fields[0]["value"]

    def test_rejected_no_reason_field_when_empty(self, notifier: SlackNotifier):
        def call():
            notifier.notify_approval_rejected("web-01", "alice", "", "req-1")

        payload = _capture_payload(notifier, call)
        fields = payload["attachments"][0]["fields"]
        reason_fields = [f for f in fields if f["title"] == "Reason"]
        assert len(reason_fields) == 0


# ---------------------------------------------------------------------------
# notify_decommission_started / completed
# ---------------------------------------------------------------------------


class TestNotifyDecommission:
    def test_decommission_started_color(self, notifier: SlackNotifier):
        def call():
            notifier.notify_decommission_started("web-01", "req-1")

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_DECOM

    def test_decommission_completed_color(self, notifier: SlackNotifier):
        def call():
            notifier.notify_decommission_completed("web-01", "req-1")

        payload = _capture_payload(notifier, call)
        assert payload["attachments"][0]["color"] == COLOR_NEUTRAL


# ---------------------------------------------------------------------------
# _build_attachment
# ---------------------------------------------------------------------------


class TestBuildAttachment:
    def test_attachment_has_required_keys(self, notifier: SlackNotifier):
        attachment = notifier._build_attachment(
            color=COLOR_INFO,
            title="Test",
            text="Test text",
            fields=[],
            request_id="req-001",
        )
        assert "color" in attachment
        assert "title" in attachment
        assert "text" in attachment
        assert "fields" in attachment
        assert "footer" in attachment
        assert "ts" in attachment
        assert "title_link" in attachment

    def test_title_link_contains_request_id(self, notifier: SlackNotifier):
        attachment = notifier._build_attachment(
            color=COLOR_INFO,
            title="T",
            text="t",
            fields=[],
            request_id="req-xyz",
        )
        assert "req-xyz" in attachment["title_link"]

    def test_footer_is_anvilops(self, notifier: SlackNotifier):
        attachment = notifier._build_attachment(
            color=COLOR_SUCCESS, title="T", text="t", fields=[], request_id="r"
        )
        assert attachment["footer"] == "AnvilOps"

    def test_app_url_trailing_slash_stripped(self):
        n = SlackNotifier(
            webhook_url="https://hooks.slack.com/x",
            enabled=True,
            app_url="http://localhost:3000/",
        )
        attachment = n._build_attachment(
            color=COLOR_INFO, title="T", text="t", fields=[], request_id="r"
        )
        # should not have double slash
        assert "//requests" not in attachment["title_link"]


# ---------------------------------------------------------------------------
# _format_duration
# ---------------------------------------------------------------------------


class TestFormatDuration:
    def test_zero_seconds(self):
        assert SlackNotifier._format_duration(0) == "0s"

    def test_negative_seconds(self):
        assert SlackNotifier._format_duration(-10) == "0s"

    def test_seconds_only(self):
        assert SlackNotifier._format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        assert SlackNotifier._format_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self):
        assert SlackNotifier._format_duration(3661) == "1h 1m 1s"

    def test_exactly_one_minute(self):
        assert SlackNotifier._format_duration(60) == "1m"

    def test_exactly_one_hour(self):
        assert SlackNotifier._format_duration(3600) == "1h"


# ---------------------------------------------------------------------------
# get_slack_notifier factory
# ---------------------------------------------------------------------------


class TestGetSlackNotifier:
    def test_returns_slack_notifier_instance(self):
        # settings is imported inside get_slack_notifier, patch at app.core.config
        with patch("app.core.config.settings") as mock_settings:
            mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
            mock_settings.SLACK_ENABLED = True
            mock_settings.SLACK_APP_URL = "http://localhost:3000"
            mock_settings.SLACK_CHANNEL = "#test"

            notifier = get_slack_notifier()

        assert isinstance(notifier, SlackNotifier)
        assert notifier.enabled is True
