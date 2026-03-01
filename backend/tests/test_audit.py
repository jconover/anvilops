"""Unit tests for AuditLogger (async and sync paths) and AuditActions.

All database interactions are fully mocked -- no real DB connections needed.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.audit import AuditActions, AuditLogger

# ---------------------------------------------------------------------------
# AuditActions constants
# ---------------------------------------------------------------------------


class TestAuditActionsConstants:
    def test_server_created_value(self):
        assert AuditActions.SERVER_CREATED == "server.created"

    def test_server_approved_value(self):
        assert AuditActions.SERVER_APPROVED == "server.approved"

    def test_server_rejected_value(self):
        assert AuditActions.SERVER_REJECTED == "server.rejected"

    def test_server_build_started_value(self):
        assert AuditActions.SERVER_BUILD_STARTED == "server.build_started"

    def test_server_build_completed_value(self):
        assert AuditActions.SERVER_BUILD_COMPLETED == "server.build_completed"

    def test_server_build_failed_value(self):
        assert AuditActions.SERVER_BUILD_FAILED == "server.build_failed"

    def test_terraform_lifecycle_constants(self):
        assert AuditActions.SERVER_TERRAFORM_STARTED == "server.terraform_started"
        assert AuditActions.SERVER_TERRAFORM_COMPLETED == "server.terraform_completed"
        assert AuditActions.SERVER_TERRAFORM_FAILED == "server.terraform_failed"

    def test_awx_lifecycle_constants(self):
        assert AuditActions.SERVER_AWX_STARTED == "server.awx_started"
        assert AuditActions.SERVER_AWX_COMPLETED == "server.awx_completed"
        assert AuditActions.SERVER_AWX_FAILED == "server.awx_failed"

    def test_puppet_lifecycle_constants(self):
        assert AuditActions.SERVER_PUPPET_STARTED == "server.puppet_started"
        assert AuditActions.SERVER_PUPPET_COMPLETED == "server.puppet_completed"
        assert AuditActions.SERVER_PUPPET_FAILED == "server.puppet_failed"

    def test_template_constants(self):
        assert AuditActions.TEMPLATE_CREATED == "template.created"
        assert AuditActions.TEMPLATE_UPDATED == "template.updated"
        assert AuditActions.TEMPLATE_DELETED == "template.deleted"

    def test_auth_constants(self):
        assert AuditActions.AUTH_LOGIN == "auth.login"
        assert AuditActions.AUTH_LOGOUT == "auth.logout"
        assert AuditActions.AUTH_LOGIN_FAILED == "auth.login_failed"

    def test_system_constants(self):
        assert AuditActions.SYSTEM_STARTUP == "system.startup"
        assert AuditActions.SYSTEM_ERROR == "system.error"

    def test_decommission_constants(self):
        assert AuditActions.SERVER_DECOMMISSION_STARTED == "server.decommission_started"
        assert AuditActions.SERVER_DECOMMISSION_COMPLETED == "server.decommission_completed"
        assert AuditActions.SERVER_DELETED == "server.deleted"

    def test_all_values_use_dot_notation(self):
        """All action constant values must follow the dot-separated convention."""
        for attr in dir(AuditActions):
            if attr.startswith("_"):
                continue
            value = getattr(AuditActions, attr)
            if isinstance(value, str):
                assert "." in value, f"{attr} value '{value}' missing dot separator"


# ---------------------------------------------------------------------------
# AuditLogger.log_async — happy path
# ---------------------------------------------------------------------------


class TestAuditLoggerAsync:
    def _make_session(self):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_log_async_adds_entry_and_flushes(self):
        session = self._make_session()
        await AuditLogger.log_async(
            db=session,
            action=AuditActions.SERVER_CREATED,
            category="server",
            actor_email="user@example.com",
            resource_type="server_request",
            resource_id="uuid-1234",
            resource_name="PROD-WEB-01",
        )
        session.add.assert_called_once()
        session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_async_entry_has_correct_action(self):
        from app.models.audit import AuditLog

        session = self._make_session()
        await AuditLogger.log_async(
            db=session,
            action=AuditActions.SERVER_BUILD_COMPLETED,
            category="server",
        )
        log_entry = session.add.call_args[0][0]
        assert isinstance(log_entry, AuditLog)
        assert log_entry.action == AuditActions.SERVER_BUILD_COMPLETED

    @pytest.mark.asyncio
    async def test_log_async_entry_has_correct_category(self):
        session = self._make_session()
        await AuditLogger.log_async(
            db=session,
            action=AuditActions.TEMPLATE_CREATED,
            category="template",
        )
        log_entry = session.add.call_args[0][0]
        assert log_entry.category == "template"

    @pytest.mark.asyncio
    async def test_log_async_default_status_is_success(self):
        session = self._make_session()
        await AuditLogger.log_async(
            db=session,
            action=AuditActions.AUTH_LOGIN,
            category="auth",
        )
        log_entry = session.add.call_args[0][0]
        assert log_entry.status == "success"

    @pytest.mark.asyncio
    async def test_log_async_passes_all_optional_fields(self):
        session = self._make_session()
        await AuditLogger.log_async(
            db=session,
            action=AuditActions.SERVER_BUILD_FAILED,
            category="server",
            actor_email="admin@corp.com",
            actor_role="admin",
            resource_type="server_request",
            resource_id="sr-001",
            resource_name="DEV-APP-01",
            details={"step": "terraform"},
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            status="failure",
            error_message="Terraform apply failed",
        )
        log_entry = session.add.call_args[0][0]
        assert log_entry.actor_email == "admin@corp.com"
        assert log_entry.actor_role == "admin"
        assert log_entry.resource_type == "server_request"
        assert log_entry.resource_id == "sr-001"
        assert log_entry.resource_name == "DEV-APP-01"
        assert log_entry.details == {"step": "terraform"}
        assert log_entry.ip_address == "192.168.1.1"
        assert log_entry.user_agent == "Mozilla/5.0"
        assert log_entry.status == "failure"
        assert log_entry.error_message == "Terraform apply failed"

    @pytest.mark.asyncio
    async def test_log_async_timestamp_is_utc(self):
        session = self._make_session()
        await AuditLogger.log_async(
            db=session,
            action=AuditActions.SYSTEM_STARTUP,
            category="system",
        )
        log_entry = session.add.call_args[0][0]
        assert log_entry.timestamp.tzinfo is not None


# ---------------------------------------------------------------------------
# AuditLogger.log_async — error swallowing
# ---------------------------------------------------------------------------


class TestAuditLoggerAsyncErrorHandling:
    @pytest.mark.asyncio
    async def test_db_add_exception_is_swallowed(self, caplog):
        session = AsyncMock()
        session.add = MagicMock(side_effect=RuntimeError("DB write failed"))
        session.flush = AsyncMock()

        with caplog.at_level(logging.ERROR):
            # Should NOT raise
            await AuditLogger.log_async(
                db=session,
                action=AuditActions.SERVER_CREATED,
                category="server",
            )
        assert "Failed to write async audit log" in caplog.text

    @pytest.mark.asyncio
    async def test_db_flush_exception_is_swallowed(self, caplog):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock(side_effect=Exception("flush error"))

        with caplog.at_level(logging.ERROR):
            await AuditLogger.log_async(
                db=session,
                action=AuditActions.SERVER_CREATED,
                category="server",
            )
        assert "Failed to write async audit log" in caplog.text


# ---------------------------------------------------------------------------
# AuditLogger.log_sync
# ---------------------------------------------------------------------------


class TestAuditLoggerSync:
    def _make_sync_session(self):
        """Return a mock sync session that acts as a context manager."""
        session = MagicMock()
        session.__enter__ = MagicMock(return_value=session)
        session.__exit__ = MagicMock(return_value=False)
        return session

    def test_log_sync_adds_entry(self):
        from app.models.audit import AuditLog

        session = self._make_sync_session()
        with patch("app.services.audit.AuditLogger.log_sync.__wrapped__", create=True):
            pass

        with patch("app.services.db.get_sync_db", return_value=session):
            AuditLogger.log_sync(
                action=AuditActions.SERVER_BUILD_COMPLETED,
                category="server",
                resource_id="req-99",
            )
        session.add.assert_called_once()
        log_entry = session.add.call_args[0][0]
        assert isinstance(log_entry, AuditLog)
        assert log_entry.action == AuditActions.SERVER_BUILD_COMPLETED

    def test_log_sync_default_status_is_success(self):
        session = self._make_sync_session()
        with patch("app.services.db.get_sync_db", return_value=session):
            AuditLogger.log_sync(
                action=AuditActions.SERVER_PUPPET_COMPLETED,
                category="server",
            )
        log_entry = session.add.call_args[0][0]
        assert log_entry.status == "success"

    def test_log_sync_exception_is_swallowed(self, caplog):
        """If get_sync_db raises, log_sync must not propagate the error."""
        with patch(
            "app.services.db.get_sync_db",
            side_effect=RuntimeError("connection refused"),
        ):
            with caplog.at_level(logging.ERROR):
                AuditLogger.log_sync(
                    action=AuditActions.SERVER_BUILD_FAILED,
                    category="server",
                )
        assert "Failed to write sync audit log" in caplog.text

    def test_log_sync_passes_resource_fields(self):
        session = self._make_sync_session()
        with patch("app.services.db.get_sync_db", return_value=session):
            AuditLogger.log_sync(
                action=AuditActions.TEMPLATE_DELETED,
                category="template",
                resource_type="template",
                resource_id="tmpl-777",
                resource_name="SQL Server",
                details={"deleted_by": "admin"},
                status="success",
            )
        log_entry = session.add.call_args[0][0]
        assert log_entry.resource_type == "template"
        assert log_entry.resource_id == "tmpl-777"
        assert log_entry.resource_name == "SQL Server"
        assert log_entry.details == {"deleted_by": "admin"}
