"""Unit tests for SlackInteractiveHandler.

Tests signature verification, action dispatch, and response helpers.
No real Slack or HTTP connections are made.
"""

import hashlib
import hmac
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services.slack_interactive import _MAX_TIMESTAMP_AGE, SlackInteractiveHandler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SECRET = "test_signing_secret_abc123"


@pytest.fixture
def handler() -> SlackInteractiveHandler:
    return SlackInteractiveHandler(signing_secret=SECRET)


@pytest.fixture
def no_secret_handler() -> SlackInteractiveHandler:
    return SlackInteractiveHandler(signing_secret="")


def _make_signature(secret: str, timestamp: str, body: str) -> str:
    """Compute a valid Slack HMAC-SHA256 signature."""
    sig_basestring = f"v0:{timestamp}:{body}"
    return (
        "v0="
        + hmac.new(
            secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )


# ---------------------------------------------------------------------------
# verify_signature
# ---------------------------------------------------------------------------


class TestVerifySignature:
    def test_valid_signature_returns_true(self, handler: SlackInteractiveHandler):
        ts = str(int(time.time()))
        body = "payload=test_body"
        sig = _make_signature(SECRET, ts, body)
        assert handler.verify_signature(ts, body, sig) is True

    def test_wrong_signature_returns_false(self, handler: SlackInteractiveHandler):
        ts = str(int(time.time()))
        body = "payload=test_body"
        wrong_sig = "v0=" + "a" * 64
        assert handler.verify_signature(ts, body, wrong_sig) is False

    def test_missing_signing_secret_returns_false(
        self, no_secret_handler: SlackInteractiveHandler
    ):
        ts = str(int(time.time()))
        body = "some_body"
        sig = _make_signature(SECRET, ts, body)
        assert no_secret_handler.verify_signature(ts, body, sig) is False

    def test_expired_timestamp_returns_false(self, handler: SlackInteractiveHandler):
        # Timestamp older than MAX_TIMESTAMP_AGE
        old_ts = str(int(time.time()) - _MAX_TIMESTAMP_AGE - 1)
        body = "payload=test"
        sig = _make_signature(SECRET, old_ts, body)
        assert handler.verify_signature(old_ts, body, sig) is False

    def test_future_timestamp_within_window_returns_true(
        self, handler: SlackInteractiveHandler
    ):
        # Slightly in the future (within the 5-minute window)
        future_ts = str(int(time.time()) + 30)
        body = "payload=test"
        sig = _make_signature(SECRET, future_ts, body)
        assert handler.verify_signature(future_ts, body, sig) is True

    def test_invalid_timestamp_string_returns_false(
        self, handler: SlackInteractiveHandler
    ):
        assert handler.verify_signature("not-a-number", "body", "v0=sig") is False

    def test_none_timestamp_returns_false(self, handler: SlackInteractiveHandler):
        assert handler.verify_signature(None, "body", "v0=sig") is False

    def test_tampered_body_returns_false(self, handler: SlackInteractiveHandler):
        ts = str(int(time.time()))
        original_body = "payload=original"
        sig = _make_signature(SECRET, ts, original_body)
        # Tamper the body
        assert handler.verify_signature(ts, "payload=tampered", sig) is False


# ---------------------------------------------------------------------------
# handle_action — approve
# ---------------------------------------------------------------------------


class TestHandleActionApprove:
    def _approve_payload(self, request_id: str = "req-abc123", username: str = "alice") -> dict:
        return {
            "actions": [{"value": f"approve:{request_id}"}],
            "user": {"name": username, "id": "U123"},
        }

    def test_approve_returns_replace_original(self, handler: SlackInteractiveHandler):
        payload = self._approve_payload()
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            result = handler.handle_action(payload)

        assert result.get("replace_original") is True

    def test_approve_result_color_is_green(self, handler: SlackInteractiveHandler):
        payload = self._approve_payload()
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            result = handler.handle_action(payload)

        assert result["attachments"][0]["color"] == "#4CAF50"

    def test_approve_text_mentions_approver(self, handler: SlackInteractiveHandler):
        payload = self._approve_payload(username="bob")
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            result = handler.handle_action(payload)

        assert "bob" in result["attachments"][0]["text"]

    def test_approve_calls_notify_approval_granted(self, handler: SlackInteractiveHandler):
        payload = self._approve_payload(request_id="req-xyz")
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            handler.handle_action(payload)

        mock_notifier.notify_approval_granted.assert_called_once()

    def test_approve_uses_user_id_when_name_missing(self, handler: SlackInteractiveHandler):
        payload = {
            "actions": [{"value": "approve:req-1"}],
            "user": {"id": "U999"},  # no "name" key
        }
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            result = handler.handle_action(payload)

        assert "U999" in result["attachments"][0]["text"]


# ---------------------------------------------------------------------------
# handle_action — reject
# ---------------------------------------------------------------------------


class TestHandleActionReject:
    def _reject_payload(self, request_id: str = "req-abc123", username: str = "carol") -> dict:
        return {
            "actions": [{"value": f"reject:{request_id}"}],
            "user": {"name": username},
        }

    def test_reject_returns_replace_original(self, handler: SlackInteractiveHandler):
        payload = self._reject_payload()
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            result = handler.handle_action(payload)

        assert result.get("replace_original") is True

    def test_reject_result_color_is_red(self, handler: SlackInteractiveHandler):
        payload = self._reject_payload()
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            result = handler.handle_action(payload)

        assert result["attachments"][0]["color"] == "#F44336"

    def test_reject_text_mentions_rejector(self, handler: SlackInteractiveHandler):
        payload = self._reject_payload(username="dave")
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            result = handler.handle_action(payload)

        assert "dave" in result["attachments"][0]["text"]

    def test_reject_calls_notify_approval_rejected(self, handler: SlackInteractiveHandler):
        payload = self._reject_payload(request_id="req-rej")
        with patch("app.services.slack.get_slack_notifier") as mock_notifier_fn:
            mock_notifier = MagicMock()
            mock_notifier_fn.return_value = mock_notifier
            handler.handle_action(payload)

        mock_notifier.notify_approval_rejected.assert_called_once()


# ---------------------------------------------------------------------------
# handle_action — error cases
# ---------------------------------------------------------------------------


class TestHandleActionErrors:
    def test_empty_actions_returns_error_response(self, handler: SlackInteractiveHandler):
        payload = {"actions": [], "user": {"name": "alice"}}
        result = handler.handle_action(payload)
        assert result.get("response_type") == "ephemeral"
        assert result.get("replace_original") is False

    def test_malformed_action_value_returns_error(self, handler: SlackInteractiveHandler):
        payload = {
            "actions": [{"value": "no_colon_here"}],
            "user": {"name": "alice"},
        }
        result = handler.handle_action(payload)
        assert result.get("response_type") == "ephemeral"

    def test_unknown_action_type_returns_error(self, handler: SlackInteractiveHandler):
        payload = {
            "actions": [{"value": "unknown_action:req-1"}],
            "user": {"name": "alice"},
        }
        result = handler.handle_action(payload)
        assert result.get("response_type") == "ephemeral"

    def test_exception_in_handle_action_returns_error(self, handler: SlackInteractiveHandler):
        # Cause an exception by providing a non-subscriptable actions value
        payload = {"actions": "not-a-list", "user": {"name": "alice"}}
        result = handler.handle_action(payload)
        assert result.get("response_type") == "ephemeral"

    def test_notifier_exception_still_returns_replacement_message(
        self, handler: SlackInteractiveHandler
    ):
        """If the notifier raises, _handle_approve still returns a valid response."""
        payload = {
            "actions": [{"value": "approve:req-fail"}],
            "user": {"name": "alice"},
        }
        with patch(
            "app.services.slack.get_slack_notifier",
            side_effect=RuntimeError("notifier unavailable"),
        ):
            result = handler.handle_action(payload)

        # Should still return a replacement message, not an error response
        assert result.get("replace_original") is True


# ---------------------------------------------------------------------------
# _replacement_message
# ---------------------------------------------------------------------------


class TestReplacementMessage:
    def test_replace_original_is_true(self):
        result = SlackInteractiveHandler._replacement_message(
            text="Approved", color="#4CAF50", request_id="req-1"
        )
        assert result["replace_original"] is True

    def test_text_is_in_attachment(self):
        result = SlackInteractiveHandler._replacement_message(
            text="Rejected by Alice", color="#F44336", request_id="req-2"
        )
        assert result["attachments"][0]["text"] == "Rejected by Alice"

    def test_color_is_set(self):
        result = SlackInteractiveHandler._replacement_message(
            text="T", color="#AABBCC", request_id="r"
        )
        assert result["attachments"][0]["color"] == "#AABBCC"

    def test_footer_is_anvilops(self):
        result = SlackInteractiveHandler._replacement_message(
            text="T", color="#000", request_id="r"
        )
        assert result["attachments"][0]["footer"] == "AnvilOps"


# ---------------------------------------------------------------------------
# _error_response
# ---------------------------------------------------------------------------


class TestErrorResponse:
    def test_response_type_is_ephemeral(self):
        result = SlackInteractiveHandler._error_response("Something went wrong.")
        assert result["response_type"] == "ephemeral"

    def test_replace_original_is_false(self):
        result = SlackInteractiveHandler._error_response("Error!")
        assert result["replace_original"] is False

    def test_text_contains_message(self):
        result = SlackInteractiveHandler._error_response("Invalid action.")
        assert "Invalid action." in result["text"]

    def test_text_contains_warning_emoji_prefix(self):
        result = SlackInteractiveHandler._error_response("Msg")
        assert ":warning:" in result["text"]


# ---------------------------------------------------------------------------
# MAX_TIMESTAMP_AGE constant
# ---------------------------------------------------------------------------


class TestMaxTimestampAge:
    def test_max_age_is_300_seconds(self):
        assert _MAX_TIMESTAMP_AGE == 300
