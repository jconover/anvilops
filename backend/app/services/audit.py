"""Audit logging service for AnvilOps.

Provides both async (for FastAPI routes) and sync (for Celery tasks)
methods to record audit events. All logging is best-effort -- audit
failures never block the primary operation.

Usage in a FastAPI route::

    from app.services.audit import AuditLogger, AuditActions

    await AuditLogger.log_async(
        db=db,
        action=AuditActions.SERVER_CREATED,
        category="server",
        actor_email="user@example.com",
        resource_type="server_request",
        resource_id=str(server.id),
        resource_name=server.server_name,
    )

Usage in a Celery task::

    from app.services.audit import AuditLogger, AuditActions

    AuditLogger.log_sync(
        action=AuditActions.SERVER_BUILD_COMPLETED,
        category="server",
        resource_type="server_request",
        resource_id=server_request_id,
    )
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditActions:
    """Pre-defined action constants for consistency across the codebase.

    Naming convention: ``<RESOURCE>_<VERB>`` using dot-separated
    lowercase strings (e.g. ``server.created``).
    """

    # Server lifecycle
    SERVER_CREATED = "server.created"
    SERVER_APPROVED = "server.approved"
    SERVER_REJECTED = "server.rejected"
    SERVER_BUILD_STARTED = "server.build_started"
    SERVER_BUILD_COMPLETED = "server.build_completed"
    SERVER_BUILD_FAILED = "server.build_failed"
    SERVER_DECOMMISSION_STARTED = "server.decommission_started"
    SERVER_DECOMMISSION_COMPLETED = "server.decommission_completed"
    SERVER_DELETED = "server.deleted"

    # Build pipeline steps
    SERVER_TERRAFORM_STARTED = "server.terraform_started"
    SERVER_TERRAFORM_COMPLETED = "server.terraform_completed"
    SERVER_TERRAFORM_FAILED = "server.terraform_failed"
    SERVER_AWX_STARTED = "server.awx_started"
    SERVER_AWX_COMPLETED = "server.awx_completed"
    SERVER_AWX_FAILED = "server.awx_failed"
    SERVER_PUPPET_STARTED = "server.puppet_started"
    SERVER_PUPPET_COMPLETED = "server.puppet_completed"
    SERVER_PUPPET_FAILED = "server.puppet_failed"

    # Template management
    TEMPLATE_CREATED = "template.created"
    TEMPLATE_UPDATED = "template.updated"
    TEMPLATE_DELETED = "template.deleted"

    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_LOGIN_FAILED = "auth.login_failed"

    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_ERROR = "system.error"


class AuditLogger:
    """Record audit events to the database.

    All methods swallow exceptions so that an audit failure never
    prevents the primary operation from completing.
    """

    @staticmethod
    async def log_async(
        db: AsyncSession,
        action: str,
        category: str,
        *,
        actor_email: str | None = None,
        actor_role: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        resource_name: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        """Record an audit event asynchronously (for use in FastAPI routes).

        The audit log is flushed but *not* committed -- the caller's
        session commit (typically the ``get_db`` dependency) will
        persist it along with the rest of the transaction.

        Parameters
        ----------
        db:
            An async SQLAlchemy session (injected via ``get_db``).
        action:
            Dot-separated action identifier. Use ``AuditActions`` constants.
        category:
            High-level grouping: ``"server"``, ``"template"``, ``"auth"``,
            ``"system"``.
        actor_email:
            Email of the user who triggered the action, if known.
        actor_role:
            RBAC role of the actor at the time of the action.
        resource_type:
            Type of affected resource (``"server_request"``, ``"template"``).
        resource_id:
            UUID (as string) of the affected resource.
        resource_name:
            Human-readable name of the affected resource.
        details:
            Arbitrary JSON-serialisable dict with extra context (e.g.
            old/new values during an update).
        ip_address:
            Client IP address.
        user_agent:
            Client User-Agent header (truncated to 500 chars).
        status:
            Outcome of the action: ``"success"``, ``"failure"``, or
            ``"error"``.
        error_message:
            Error details when status is ``"failure"`` or ``"error"``.
        """
        try:
            log_entry = AuditLog(
                timestamp=datetime.now(timezone.utc),
                action=action,
                category=category,
                actor_email=actor_email,
                actor_role=actor_role,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                error_message=error_message,
            )
            db.add(log_entry)
            await db.flush()
        except Exception as exc:
            logger.error("Failed to write async audit log: %s", exc)

    @staticmethod
    def log_sync(
        action: str,
        category: str,
        *,
        actor_email: str | None = None,
        actor_role: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        resource_name: str | None = None,
        details: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        """Record an audit event synchronously (for use in Celery tasks).

        Opens its own database session and commits independently so that
        the audit record is persisted even if the calling task later
        fails.

        Parameters are identical to :meth:`log_async`.
        """
        try:
            from app.services.db import get_sync_db

            with get_sync_db() as session:
                log_entry = AuditLog(
                    timestamp=datetime.now(timezone.utc),
                    action=action,
                    category=category,
                    actor_email=actor_email,
                    actor_role=actor_role,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    resource_name=resource_name,
                    details=details,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status=status,
                    error_message=error_message,
                )
                session.add(log_entry)
                # The context manager commits on exit.
        except Exception as exc:
            logger.error("Failed to write sync audit log: %s", exc)
