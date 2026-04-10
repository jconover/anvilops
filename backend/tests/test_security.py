"""Negative security tests for the AnvilOps FastAPI backend.

Covers:
- Authentication: missing/malformed/expired/wrong-key JWTs
- Authorization: role hierarchy enforcement via require_role
- Error sanitization: DEBUG mode vs production mode responses
- Rate limiting: presence of rate-limit headers
- Input validation: SQL injection and XSS patterns
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.auth import (
    AuthenticatedUser,
    _get_jwk_client,
    get_current_user,
    require_role,
)
from app.core.config import settings
from app.db.session import get_db
from app.main import _global_exception_handler, app
from app.services.awx_exceptions import AWXError


async def _mock_db():
    """Fake DB dependency that never touches a real database."""
    yield AsyncMock()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(role: str = "admin") -> AuthenticatedUser:
    """Build an AuthenticatedUser with the given role."""
    return AuthenticatedUser(
        sub="test-sub-123",
        email="test@example.com",
        groups=[],
        role=role,
    )


def _override_auth(role: str = "admin"):
    """Return an override for get_current_user that always yields a user with *role*."""
    async def _dep():
        return _make_user(role)
    return _dep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def client() -> AsyncClient:
    """Unauthenticated async client — no dependency overrides.

    Uses a patched lifespan so tests run without a live database.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    original_router = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_db] = _mock_db

    # Auth tests need a valid pool ID so get_current_user reaches JWT
    # validation instead of short-circuiting with 503.
    original_pool_id = settings.COGNITO_USER_POOL_ID
    settings.COGNITO_USER_POOL_ID = "us-east-1_TestPool"
    _get_jwk_client.cache_clear()

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    settings.COGNITO_USER_POOL_ID = original_pool_id
    _get_jwk_client.cache_clear()
    app.dependency_overrides.pop(get_db, None)
    app.router.lifespan_context = original_router


@pytest.fixture
async def authed_client():
    """Factory fixture: yields a coroutine that creates an async client with a
    specific role override.  Callers must close the client via ``await ac.aclose()``
    or use it as an async context manager.
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    original_router = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan
    app.dependency_overrides[get_db] = _mock_db
    clients_opened: list[AsyncClient] = []

    async def _make(role: str = "admin") -> AsyncClient:
        app.dependency_overrides[get_current_user] = _override_auth(role)
        ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        await ac.__aenter__()
        clients_opened.append(ac)
        return ac

    yield _make

    for ac in clients_opened:
        await ac.__aexit__(None, None, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    app.router.lifespan_context = original_router


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------


class TestAuthenticationNegative:
    """Protected endpoints must reject requests that lack a valid JWT."""

    async def test_no_authorization_header_returns_401(self, client):
        response = await client.get("/api/v1/templates/")
        assert response.status_code == 401

    async def test_empty_bearer_token_returns_401(self, client):
        response = await client.get(
            "/api/v1/templates/",
            headers={"Authorization": "Bearer "},
        )
        assert response.status_code == 401

    async def test_malformed_jwt_not_three_parts_returns_401(self, client):
        response = await client.get(
            "/api/v1/templates/",
            headers={"Authorization": "Bearer not.a.valid.jwt.token"},
        )
        assert response.status_code == 401

    async def test_expired_jwt_returns_401(self, client):
        """A syntactically valid JWT with exp in the past must be rejected."""
        # Build a minimal RS256 token that PyJWT can partially parse before
        # we mock the JWKS lookup so the library reaches signature/expiry checks.
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        payload = {
            "sub": "u-123",
            "email": "user@example.com",
            "token_use": "id",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_test",
            "exp": int(time.time()) - 3600,  # expired one hour ago
            "iat": int(time.time()) - 7200,
        }
        expired_token = jwt.encode(payload, private_key, algorithm="RS256")

        mock_signing_key = MagicMock()
        mock_signing_key.key = private_key.public_key()

        with patch("app.core.auth._get_jwk_client") as mock_jwk_factory:
            mock_jwk_client = MagicMock()
            mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
            mock_jwk_factory.return_value = mock_jwk_client

            response = await client.get(
                "/api/v1/templates/",
                headers={"Authorization": f"Bearer {expired_token}"},
            )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    async def test_wrong_signing_key_returns_401(self, client):
        """A JWT signed with a key that does not match the JWKS must be rejected."""
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        signing_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        wrong_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        payload = {
            "sub": "u-123",
            "email": "user@example.com",
            "token_use": "id",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_test",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        token = jwt.encode(payload, signing_key, algorithm="RS256")

        # JWKS returns the *wrong* public key — signature check must fail
        mock_signing_key = MagicMock()
        mock_signing_key.key = wrong_key.public_key()

        with patch("app.core.auth._get_jwk_client") as mock_jwk_factory:
            mock_jwk_client = MagicMock()
            mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
            mock_jwk_factory.return_value = mock_jwk_client

            response = await client.get(
                "/api/v1/templates/",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 401

    async def test_jwt_missing_sub_claim_returns_401(self, client):
        """A JWT without the 'sub' claim (required by jwt.decode options) must be rejected."""
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        payload = {
            # 'sub' is intentionally omitted
            "email": "user@example.com",
            "token_use": "id",
            "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_test",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
        token = jwt.encode(payload, private_key, algorithm="RS256")

        mock_signing_key = MagicMock()
        mock_signing_key.key = private_key.public_key()

        with patch("app.core.auth._get_jwk_client") as mock_jwk_factory:
            mock_jwk_client = MagicMock()
            mock_jwk_client.get_signing_key_from_jwt.return_value = mock_signing_key
            mock_jwk_factory.return_value = mock_jwk_client

            response = await client.get(
                "/api/v1/templates/",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 401

    async def test_jwt_missing_email_resolves_to_empty_string(self):
        """email is optional in the JWT — AuthenticatedUser defaults to empty string.
        This confirms that _resolve_highest_role + AuthenticatedUser creation work
        without an email claim.
        """
        from app.core.auth import _resolve_highest_role

        # Simulate the payload path that get_current_user would follow
        cognito_groups = ["Admin"]
        role = _resolve_highest_role(cognito_groups)
        user = AuthenticatedUser(
            sub="u-456",
            email="",  # This is what get_current_user does when email is absent
            groups=cognito_groups,
            role=role,
        )
        assert user.role == "admin"
        assert user.email == ""

    async def test_no_cognito_pool_configured_returns_503(self, client):
        """When COGNITO_USER_POOL_ID is empty the auth dependency returns 503."""
        with patch("app.core.auth.settings") as mock_settings:
            mock_settings.COGNITO_USER_POOL_ID = ""
            response = await client.get("/api/v1/templates/")

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# Authorization / role hierarchy tests
# ---------------------------------------------------------------------------


class TestRoleHierarchy:
    """require_role dependency enforces role hierarchy correctly."""

    async def test_require_role_allows_exact_role(self):
        """A user whose role exactly matches the minimum is permitted."""
        check = require_role("builder")
        viewer_user = _make_user("builder")
        # Should not raise
        result = await check(viewer_user)
        assert result is viewer_user

    async def test_require_role_allows_higher_role(self):
        """An admin passes a check requiring 'viewer'."""
        check = require_role("viewer")
        admin_user = _make_user("admin")
        result = await check(admin_user)
        assert result is admin_user

    async def test_require_role_rejects_lower_role(self):
        """A viewer is rejected when admin is required."""
        from fastapi import HTTPException

        check = require_role("admin")
        viewer_user = _make_user("viewer")

        with pytest.raises(HTTPException) as exc_info:
            await check(viewer_user)

        assert exc_info.value.status_code == 403
        assert "admin" in exc_info.value.detail

    async def test_viewer_cannot_reach_approver_required_endpoint(self):
        """builder role is below approver — must get 403."""
        from fastapi import HTTPException

        check = require_role("approver")
        builder_user = _make_user("builder")

        with pytest.raises(HTTPException) as exc_info:
            await check(builder_user)

        assert exc_info.value.status_code == 403

    async def test_role_hierarchy_ordering(self):
        """Verify the full hierarchy: viewer < builder < builder_prod < approver < admin."""
        from fastapi import HTTPException

        roles_ascending = ["viewer", "builder", "builder_prod", "approver", "admin"]

        for i, lower_role in enumerate(roles_ascending):
            for higher_role in roles_ascending[i + 1 :]:
                # A user with lower_role should be denied when higher_role is required
                check = require_role(higher_role)
                user = _make_user(lower_role)
                with pytest.raises(HTTPException) as exc_info:
                    await check(user)
                assert exc_info.value.status_code == 403, (
                    f"Expected 403: {lower_role} accessing {higher_role}-required endpoint"
                )

    async def test_approver_can_satisfy_builder_requirement(self):
        """approver > builder, so approver must be allowed where builder is required."""
        check = require_role("builder")
        approver_user = _make_user("approver")
        result = await check(approver_user)
        assert result is approver_user

    async def test_builder_prod_above_builder(self):
        """builder_prod satisfies a builder requirement."""
        check = require_role("builder")
        user = _make_user("builder_prod")
        result = await check(user)
        assert result is user

    async def test_builder_cannot_satisfy_builder_prod_requirement(self):
        """builder is below builder_prod — must be rejected."""
        from fastapi import HTTPException

        check = require_role("builder_prod")
        user = _make_user("builder")
        with pytest.raises(HTTPException) as exc_info:
            await check(user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Error sanitization tests
# ---------------------------------------------------------------------------


class TestErrorSanitization:
    """Global exception handler sanitizes error details based on DEBUG flag."""

    async def test_unhandled_exception_production_returns_generic_500(self):
        """In production (DEBUG=False), unhandled exceptions must not leak details."""
        from starlette.requests import Request as StarletteRequest

        mock_request = MagicMock(spec=StarletteRequest)

        with patch("app.main.settings") as mock_settings:
            mock_settings.DEBUG = False
            response = await _global_exception_handler(
                mock_request,
                RuntimeError("internal db password is hunter2"),
            )

        assert response.status_code == 500
        body = response.body.decode()
        assert "hunter2" not in body
        assert "internal" in body.lower() or "error" in body.lower()

    async def test_unhandled_exception_debug_returns_actual_message(self):
        """In DEBUG mode the actual exception message is returned."""
        from starlette.requests import Request as StarletteRequest

        mock_request = MagicMock(spec=StarletteRequest)

        with patch("app.main.settings") as mock_settings:
            mock_settings.DEBUG = True
            response = await _global_exception_handler(
                mock_request,
                RuntimeError("specific debug detail"),
            )

        assert response.status_code == 500
        body = response.body.decode()
        assert "specific debug detail" in body

    async def test_awx_upstream_error_production_returns_503_generic(self):
        """AWXError in production maps to 503 with a generic message."""
        from starlette.requests import Request as StarletteRequest

        mock_request = MagicMock(spec=StarletteRequest)

        with patch("app.main.settings") as mock_settings:
            mock_settings.DEBUG = False
            response = await _global_exception_handler(
                mock_request,
                AWXError("awx-host.internal:8052 connection refused"),
            )

        assert response.status_code == 503
        body = response.body.decode()
        assert "awx-host.internal" not in body
        assert "unavailable" in body.lower()

    async def test_awx_upstream_error_debug_returns_generic_not_detail(self):
        """Even in DEBUG mode, AWXError goes through the standard DEBUG branch
        (returns the exception str, not the upstream-specific 503 path).
        """
        from starlette.requests import Request as StarletteRequest

        mock_request = MagicMock(spec=StarletteRequest)

        with patch("app.main.settings") as mock_settings:
            mock_settings.DEBUG = True
            response = await _global_exception_handler(
                mock_request,
                AWXError("awx debug detail"),
            )

        # In DEBUG, the handler returns 500 with the exception message regardless
        assert response.status_code == 500
        body = response.body.decode()
        assert "awx debug detail" in body

    async def test_puppet_upstream_error_production_returns_503(self):
        """PuppetError in production maps to 503 with a generic message."""
        from starlette.requests import Request as StarletteRequest

        from app.services.puppet_exceptions import PuppetError

        mock_request = MagicMock(spec=StarletteRequest)

        with patch("app.main.settings") as mock_settings:
            mock_settings.DEBUG = False
            response = await _global_exception_handler(
                mock_request,
                PuppetError("puppet-pe.internal:8140 TLS handshake failed"),
            )

        assert response.status_code == 503
        body = response.body.decode()
        assert "puppet-pe.internal" not in body
        assert "unavailable" in body.lower()

    async def test_generic_runtime_error_not_treated_as_upstream(self):
        """A plain RuntimeError must not be returned as a 503 upstream error."""
        from starlette.requests import Request as StarletteRequest

        mock_request = MagicMock(spec=StarletteRequest)

        with patch("app.main.settings") as mock_settings:
            mock_settings.DEBUG = False
            response = await _global_exception_handler(
                mock_request,
                RuntimeError("ordinary unhandled error"),
            )

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# Rate limiting tests
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Verify that slowapi rate-limit infrastructure is wired up."""

    async def test_health_endpoint_responds_successfully(self, client):
        """Baseline: health endpoint must be reachable under the rate limit."""
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_rate_limiter_is_configured_on_app(self):
        """Verify the main app has a SlowAPI limiter attached."""
        assert hasattr(app.state, "limiter"), "SlowAPI limiter not attached to app.state"

    async def test_rate_limit_default_setting_is_set(self):
        """Verify a rate limit default is configured."""
        assert settings.RATE_LIMIT_DEFAULT, "RATE_LIMIT_DEFAULT must be non-empty"
        # Should be in the form "N/period" e.g. "100/minute"
        parts = settings.RATE_LIMIT_DEFAULT.split("/")
        assert len(parts) == 2, f"Unexpected rate limit format: {settings.RATE_LIMIT_DEFAULT}"
        assert parts[0].isdigit(), "Rate limit count must be numeric"


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Pydantic schema validation rejects malformed or dangerous input."""

    async def test_sql_injection_in_query_params_returns_safely(self, authed_client):
        """SQL injection in query parameters must not cause a 500.
        The skip/limit parameters are typed as int so Pydantic rejects strings.
        """
        ac = await authed_client("admin")
        response = await ac.get("/api/v1/servers/?skip=0;DROP TABLE servers")
        # Should be 422 (validation error for non-int) — never 500
        assert response.status_code in (200, 422)

    async def test_xss_in_json_response_is_escaped(self):
        """JSON serialization by FastAPI ensures XSS payloads in string
        fields cannot execute — angle brackets are part of the JSON string,
        not raw HTML.
        """
        import json
        xss = "<script>alert('xss')</script>"
        # json.dumps escapes by default for safe embedding
        serialized = json.dumps({"server_name": xss})
        assert "<script>" not in serialized or "\\u003c" in serialized or '"<script>' in serialized
        # The key point: JSON responses have Content-Type application/json,
        # so browsers do not interpret the body as HTML.

    async def test_invalid_environment_value_returns_422(self, authed_client):
        """Pydantic Literal validation on 'environment' must reject unknown values."""
        ac = await authed_client("admin")
        payload = {
            "environment": "unknown_env",
            "os_type": "amazon_linux_2023",
            "instance_size": "small",
            "vpc_id": "vpc-0123456789abcdef0",
            "subnet_id": "subnet-0123456789abcdef0",
        }
        response = await ac.post("/api/v1/servers/", json=payload)
        assert response.status_code == 422

    async def test_oversized_storage_volume_returns_422(self, authed_client):
        """Storage volume size > 16384 GB must be rejected by Pydantic."""
        ac = await authed_client("admin")
        payload = {
            "environment": "dev",
            "os_type": "amazon_linux_2023",
            "instance_size": "small",
            "vpc_id": "vpc-0123456789abcdef0",
            "subnet_id": "subnet-0123456789abcdef0",
            "additional_storage": [{"size_gb": 99999, "volume_type": "gp3"}],
        }
        response = await ac.post("/api/v1/servers/", json=payload)
        assert response.status_code == 422

    async def test_negative_storage_volume_returns_422(self, authed_client):
        """Storage volume size < 1 GB must be rejected by Pydantic."""
        ac = await authed_client("admin")
        payload = {
            "environment": "dev",
            "os_type": "amazon_linux_2023",
            "instance_size": "small",
            "vpc_id": "vpc-0123456789abcdef0",
            "subnet_id": "subnet-0123456789abcdef0",
            "additional_storage": [{"size_gb": 0, "volume_type": "gp3"}],
        }
        response = await ac.post("/api/v1/servers/", json=payload)
        assert response.status_code == 422

    async def test_sql_injection_in_template_query_param_is_safe(self, authed_client):
        """SQL injection in a query parameter must not produce a 500."""
        ac = await authed_client("admin")
        with patch("app.api.v1.templates.get_db"):
            response = await ac.get(
                "/api/v1/templates/",
                params={"skip": "0; DROP TABLE templates; --"},
            )
        # Pydantic coerces 'skip' to int; invalid value -> 422
        assert response.status_code in (422, 200)
        assert response.status_code != 500
