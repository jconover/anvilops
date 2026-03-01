"""Tests for the audit middleware (app.middleware.audit).

Validates that get_audit_context correctly extracts IP, User-Agent,
and actor information from incoming FastAPI requests.
"""

from unittest.mock import MagicMock

from app.middleware.audit import get_audit_context


def _make_request(
    headers: dict | None = None,
    client_host: str | None = "127.0.0.1",
    state_attrs: dict | None = None,
):
    """Build a mock FastAPI Request with configurable headers and state."""
    request = MagicMock()
    request.headers = headers or {}

    if client_host is not None:
        request.client = MagicMock()
        request.client.host = client_host
    else:
        request.client = None

    # Set up request.state so getattr works correctly
    state = MagicMock(spec=[])
    if state_attrs:
        for k, v in state_attrs.items():
            setattr(state, k, v)
    request.state = state

    return request


class TestGetAuditContextIP:
    """IP address extraction from request."""

    def test_direct_client_ip(self):
        request = _make_request(client_host="192.168.1.10")
        ctx = get_audit_context(request)
        assert ctx["ip_address"] == "192.168.1.10"

    def test_x_forwarded_for_single(self):
        request = _make_request(
            headers={"x-forwarded-for": "10.0.0.1"},
            client_host="192.168.1.10",
        )
        ctx = get_audit_context(request)
        assert ctx["ip_address"] == "10.0.0.1"

    def test_x_forwarded_for_multiple(self):
        """Should take the leftmost (original client) IP."""
        request = _make_request(
            headers={"x-forwarded-for": "10.0.0.1, 10.0.0.2, 10.0.0.3"},
            client_host="192.168.1.10",
        )
        ctx = get_audit_context(request)
        assert ctx["ip_address"] == "10.0.0.1"

    def test_x_forwarded_for_with_spaces(self):
        request = _make_request(
            headers={"x-forwarded-for": "  203.0.113.50 , 198.51.100.1 "},
        )
        ctx = get_audit_context(request)
        assert ctx["ip_address"] == "203.0.113.50"

    def test_no_client_returns_none(self):
        request = _make_request(client_host=None)
        ctx = get_audit_context(request)
        assert ctx["ip_address"] is None


class TestGetAuditContextUserAgent:
    """User-Agent extraction."""

    def test_user_agent_present(self):
        request = _make_request(
            headers={"user-agent": "Mozilla/5.0 (X11; Linux)"}
        )
        ctx = get_audit_context(request)
        assert ctx["user_agent"] == "Mozilla/5.0 (X11; Linux)"

    def test_user_agent_missing_returns_none(self):
        request = _make_request(headers={})
        ctx = get_audit_context(request)
        assert ctx["user_agent"] is None

    def test_user_agent_truncated_to_500(self):
        long_ua = "A" * 600
        request = _make_request(headers={"user-agent": long_ua})
        ctx = get_audit_context(request)
        assert len(ctx["user_agent"]) == 500

    def test_empty_user_agent_returns_none(self):
        request = _make_request(headers={"user-agent": ""})
        ctx = get_audit_context(request)
        assert ctx["user_agent"] is None


class TestGetAuditContextActor:
    """Actor info from request.state (set by auth middleware)."""

    def test_actor_from_state(self):
        request = _make_request(
            state_attrs={
                "actor_email": "admin@example.com",
                "actor_role": "admin",
            }
        )
        ctx = get_audit_context(request)
        assert ctx["actor_email"] == "admin@example.com"
        assert ctx["actor_role"] == "admin"

    def test_no_actor_returns_none(self):
        request = _make_request()
        ctx = get_audit_context(request)
        assert ctx["actor_email"] is None
        assert ctx["actor_role"] is None

    def test_return_keys_complete(self):
        """All expected keys are always present."""
        request = _make_request()
        ctx = get_audit_context(request)
        assert set(ctx.keys()) == {
            "ip_address",
            "user_agent",
            "actor_email",
            "actor_role",
        }
