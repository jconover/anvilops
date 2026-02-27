"""Unit tests for the NotificationService.

Tests both async (FastAPI) and sync (Celery) creation paths.
Database sessions are mocked -- no real DB connections required.
"""

from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import pytest

from app.services.notifications import NotificationService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock async SQLAlchemy session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# create_async
# ---------------------------------------------------------------------------


class TestCreateAsync:
    @pytest.mark.asyncio
    async def test_creates_notification_with_required_fields(
        self, mock_db: AsyncMock
    ):
        notification = await NotificationService.create_async(
            db=mock_db,
            user_email="user@example.com",
            title="Test Title",
            message="Test message body",
        )

        assert notification.user_email == "user@example.com"
        assert notification.title == "Test Title"
        assert notification.message == "Test message body"

    @pytest.mark.asyncio
    async def test_default_category_is_system(self, mock_db: AsyncMock):
        notification = await NotificationService.create_async(
            db=mock_db,
            user_email="u@example.com",
            title="T",
            message="M",
        )
        assert notification.category == "system"

    @pytest.mark.asyncio
    async def test_default_severity_is_info(self, mock_db: AsyncMock):
        notification = await NotificationService.create_async(
            db=mock_db,
            user_email="u@example.com",
            title="T",
            message="M",
        )
        assert notification.severity == "info"

    @pytest.mark.asyncio
    async def test_custom_category_and_severity(self, mock_db: AsyncMock):
        notification = await NotificationService.create_async(
            db=mock_db,
            user_email="u@example.com",
            title="Build Failed",
            message="Err",
            category="build",
            severity="error",
        )
        assert notification.category == "build"
        assert notification.severity == "error"

    @pytest.mark.asyncio
    async def test_id_is_uuid(self, mock_db: AsyncMock):
        notification = await NotificationService.create_async(
            db=mock_db,
            user_email="u@example.com",
            title="T",
            message="M",
        )
        assert isinstance(notification.id, UUID)

    @pytest.mark.asyncio
    async def test_optional_fields_are_set(self, mock_db: AsyncMock):
        notification = await NotificationService.create_async(
            db=mock_db,
            user_email="u@example.com",
            title="T",
            message="M",
            resource_type="server_request",
            resource_id="req-abc",
            action_url="/requests/req-abc",
            icon="hammer",
            details={"server_name": "web-01"},
        )
        assert notification.resource_type == "server_request"
        assert notification.resource_id == "req-abc"
        assert notification.action_url == "/requests/req-abc"
        assert notification.icon == "hammer"
        assert notification.details == {"server_name": "web-01"}

    @pytest.mark.asyncio
    async def test_db_add_and_flush_are_called(self, mock_db: AsyncMock):
        await NotificationService.create_async(
            db=mock_db,
            user_email="u@example.com",
            title="T",
            message="M",
        )
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_each_call_gets_unique_id(self, mock_db: AsyncMock):
        n1 = await NotificationService.create_async(
            db=mock_db, user_email="u@example.com", title="T1", message="M"
        )
        n2 = await NotificationService.create_async(
            db=mock_db, user_email="u@example.com", title="T2", message="M"
        )
        assert n1.id != n2.id


# ---------------------------------------------------------------------------
# create_sync
# ---------------------------------------------------------------------------


class TestCreateSync:
    def test_creates_notification_via_sync_session(self):
        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("app.services.db.get_sync_db", return_value=mock_ctx):
            NotificationService.create_sync(
                title="Sync Notification",
                message="Sync message",
                user_email="celery@example.com",
            )

        mock_session.add.assert_called_once()

    def test_swallows_exception_on_db_error(self):
        """create_sync must not raise even if the DB session fails."""
        with patch(
            "app.services.db.get_sync_db",
            side_effect=RuntimeError("DB unavailable"),
        ):
            # Should not raise
            NotificationService.create_sync(
                title="T",
                message="M",
            )

    def test_default_user_email_is_all(self):
        mock_session = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_session)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        captured = []

        def capture_add(obj):
            captured.append(obj)

        mock_session.add.side_effect = capture_add

        with patch("app.services.db.get_sync_db", return_value=mock_ctx):
            NotificationService.create_sync(title="T", message="M")

        assert captured[0].user_email == "all"


# ---------------------------------------------------------------------------
# notify_build_started (sync helper)
# ---------------------------------------------------------------------------


class TestNotifyBuildStarted:
    def test_calls_create_sync_with_build_category(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_started(
                server_name="web-01",
                request_id="req-123",
                user_email="user@example.com",
            )

        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        assert kwargs["category"] == "build"
        assert kwargs["severity"] == "info"

    def test_title_is_build_started(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_started("web-01", "req-1")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["title"] == "Build Started"

    def test_message_contains_server_name(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_started("my-server-99", "req-1")

        kwargs = mock_create.call_args.kwargs
        assert "my-server-99" in kwargs["message"]

    def test_action_url_contains_request_id(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_started("web-01", "req-abc")

        kwargs = mock_create.call_args.kwargs
        assert "req-abc" in kwargs["action_url"]

    def test_swallows_exception_if_create_sync_raises(self):
        with patch.object(
            NotificationService,
            "create_sync",
            side_effect=RuntimeError("unexpected"),
        ):
            # Should not raise
            NotificationService.notify_build_started("web-01", "req-1")


# ---------------------------------------------------------------------------
# notify_build_completed (sync helper)
# ---------------------------------------------------------------------------


class TestNotifyBuildCompleted:
    def test_category_is_build_severity_success(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_completed("web-01", "req-1")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["category"] == "build"
        assert kwargs["severity"] == "success"

    def test_title_is_build_completed(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_completed("web-01", "req-1")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["title"] == "Build Completed"

    def test_icon_is_check_circle(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_completed("web-01", "req-1")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["icon"] == "check-circle"


# ---------------------------------------------------------------------------
# notify_build_failed (sync helper)
# ---------------------------------------------------------------------------


class TestNotifyBuildFailed:
    def test_category_is_build_severity_error(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_failed("web-01", "req-1", "Terraform timeout")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["category"] == "build"
        assert kwargs["severity"] == "error"

    def test_message_contains_error(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_failed("web-01", "req-1", "AWS quota exceeded")

        kwargs = mock_create.call_args.kwargs
        assert "AWS quota exceeded" in kwargs["message"]

    def test_details_contain_error_key(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_failed("web-01", "req-1", "some error")

        kwargs = mock_create.call_args.kwargs
        assert "error" in kwargs["details"]

    def test_icon_is_alert_triangle(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_build_failed("web-01", "req-1", "err")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["icon"] == "alert-triangle"


# ---------------------------------------------------------------------------
# notify_approval_needed
# ---------------------------------------------------------------------------


class TestNotifyApprovalNeeded:
    def test_category_is_approval_severity_warning(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_approval_needed("web-01", "req-1", "production")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["category"] == "approval"
        assert kwargs["severity"] == "warning"

    def test_title_is_approval_required(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_approval_needed("web-01", "req-1", "production")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["title"] == "Approval Required"

    def test_user_email_is_all(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_approval_needed("web-01", "req-1", "production")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["user_email"] == "all"

    def test_message_contains_environment(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_approval_needed("web-01", "req-1", "production")

        kwargs = mock_create.call_args.kwargs
        assert "production" in kwargs["message"]

    def test_action_url_contains_request_id(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_approval_needed("web-01", "req-abc", "production")

        kwargs = mock_create.call_args.kwargs
        assert "req-abc" in kwargs["action_url"]

    def test_swallows_exception(self):
        with patch.object(
            NotificationService, "create_sync", side_effect=RuntimeError("DB down")
        ):
            NotificationService.notify_approval_needed("web-01", "req-1", "prod")


# ---------------------------------------------------------------------------
# notify_compliance_alert
# ---------------------------------------------------------------------------


class TestNotifyComplianceAlert:
    def test_category_is_compliance_severity_warning(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_compliance_alert(
                "web-01", "web-01.example.com", "Puppet drift detected"
            )

        kwargs = mock_create.call_args.kwargs
        assert kwargs["category"] == "compliance"
        assert kwargs["severity"] == "warning"

    def test_title_is_compliance_alert(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_compliance_alert("web-01", "cert", "issue")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["title"] == "Compliance Alert"

    def test_message_contains_issue(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_compliance_alert(
                "web-01", "cert", "SSH key drift"
            )

        kwargs = mock_create.call_args.kwargs
        assert "SSH key drift" in kwargs["message"]

    def test_details_contain_certname(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_compliance_alert(
                "web-01", "web-01.example.com", "issue"
            )

        kwargs = mock_create.call_args.kwargs
        assert kwargs["details"]["certname"] == "web-01.example.com"

    def test_icon_is_shield_alert(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_compliance_alert("web-01", "cert", "issue")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["icon"] == "shield-alert"

    def test_action_url_contains_server_name(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_compliance_alert("my-web-server", "cert", "issue")

        kwargs = mock_create.call_args.kwargs
        assert "my-web-server" in kwargs["action_url"]

    def test_resource_id_is_none(self):
        with patch.object(NotificationService, "create_sync") as mock_create:
            NotificationService.notify_compliance_alert("web-01", "cert", "issue")

        kwargs = mock_create.call_args.kwargs
        assert kwargs["resource_id"] is None

    def test_swallows_exception(self):
        with patch.object(
            NotificationService, "create_sync", side_effect=RuntimeError("DB down")
        ):
            NotificationService.notify_compliance_alert("web-01", "cert", "issue")
