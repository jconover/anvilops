"""In-app notification service for AnvilOps.

Creates and manages user notifications for build events, approvals,
compliance alerts, and system messages.  Both async (FastAPI) and
sync (Celery) methods are provided.

All public helpers are best-effort: they catch and log exceptions so that
a notification failure never breaks the calling operation.
"""

import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationService:
    """Create and manage in-app notifications."""

    # ------------------------------------------------------------------
    # Core creators
    # ------------------------------------------------------------------

    @staticmethod
    async def create_async(
        db: AsyncSession,
        user_email: str,
        title: str,
        message: str,
        category: str = "system",
        severity: str = "info",
        resource_type: str | None = None,
        resource_id: str | None = None,
        action_url: str | None = None,
        icon: str | None = None,
        details: dict | None = None,
    ) -> Notification:
        """Create a notification inside an existing async session.

        The caller is responsible for committing the session (usually the
        ``get_db`` dependency does this automatically).
        """
        notification = Notification(
            id=uuid4(),
            user_email=user_email,
            title=title,
            message=message,
            category=category,
            severity=severity,
            resource_type=resource_type,
            resource_id=resource_id,
            action_url=action_url,
            icon=icon,
            details=details,
        )
        db.add(notification)
        await db.flush()
        logger.info(
            "Created notification %s for %s: %s",
            notification.id,
            user_email,
            title,
        )
        return notification

    @staticmethod
    def create_sync(
        title: str,
        message: str,
        user_email: str = "all",
        category: str = "system",
        severity: str = "info",
        resource_type: str | None = None,
        resource_id: str | None = None,
        action_url: str | None = None,
        icon: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Create a notification synchronously (for Celery tasks).

        Opens its own sync session so callers do not need to pass one in.
        Best-effort: exceptions are logged and swallowed.
        """
        try:
            from app.services.db import get_sync_db

            with get_sync_db() as session:
                notification = Notification(
                    id=uuid4(),
                    user_email=user_email,
                    title=title,
                    message=message,
                    category=category,
                    severity=severity,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action_url=action_url,
                    icon=icon,
                    details=details,
                )
                session.add(notification)
                # session commit handled by context manager
            logger.info(
                "Created sync notification for %s: %s", user_email, title
            )
        except Exception:
            logger.exception(
                "Failed to create sync notification for %s: %s",
                user_email,
                title,
            )

    # ------------------------------------------------------------------
    # Build lifecycle helpers (sync — called from Celery tasks)
    # ------------------------------------------------------------------

    @staticmethod
    def notify_build_started(
        server_name: str,
        request_id: str,
        user_email: str = "all",
    ) -> None:
        """Notification: server build has started."""
        try:
            NotificationService.create_sync(
                title="Build Started",
                message=f"Server {server_name} build has started.",
                user_email=user_email,
                category="build",
                severity="info",
                resource_type="server_request",
                resource_id=request_id,
                action_url=f"/requests/{request_id}",
                icon="hammer",
                details={"server_name": server_name},
            )
        except Exception:
            logger.exception(
                "notify_build_started failed for %s", server_name
            )

    @staticmethod
    def notify_build_completed(
        server_name: str,
        request_id: str,
        user_email: str = "all",
    ) -> None:
        """Notification: server build completed successfully."""
        try:
            NotificationService.create_sync(
                title="Build Completed",
                message=f"Server {server_name} has been provisioned successfully.",
                user_email=user_email,
                category="build",
                severity="success",
                resource_type="server_request",
                resource_id=request_id,
                action_url=f"/requests/{request_id}",
                icon="check-circle",
                details={"server_name": server_name},
            )
        except Exception:
            logger.exception(
                "notify_build_completed failed for %s", server_name
            )

    @staticmethod
    def notify_build_failed(
        server_name: str,
        request_id: str,
        error: str,
        user_email: str = "all",
    ) -> None:
        """Notification: server build failed."""
        try:
            NotificationService.create_sync(
                title="Build Failed",
                message=f"Server {server_name} build failed: {error}",
                user_email=user_email,
                category="build",
                severity="error",
                resource_type="server_request",
                resource_id=request_id,
                action_url=f"/requests/{request_id}",
                icon="alert-triangle",
                details={"server_name": server_name, "error": error},
            )
        except Exception:
            logger.exception(
                "notify_build_failed failed for %s", server_name
            )

    # ------------------------------------------------------------------
    # Approval helpers
    # ------------------------------------------------------------------

    @staticmethod
    def notify_approval_needed(
        server_name: str,
        request_id: str,
        environment: str,
    ) -> None:
        """Notification: a production / large-instance request needs approval.

        Sent to all users (approvers will see it via the "approval" category
        filter); fine-grained targeting can be added when RBAC is wired up.
        """
        try:
            NotificationService.create_sync(
                title="Approval Required",
                message=(
                    f"Server {server_name} ({environment}) requires approval "
                    f"before provisioning can proceed."
                ),
                user_email="all",
                category="approval",
                severity="warning",
                resource_type="server_request",
                resource_id=request_id,
                action_url=f"/approvals/{request_id}",
                icon="shield-check",
                details={
                    "server_name": server_name,
                    "environment": environment,
                },
            )
        except Exception:
            logger.exception(
                "notify_approval_needed failed for %s", server_name
            )

    # ------------------------------------------------------------------
    # Compliance helpers
    # ------------------------------------------------------------------

    @staticmethod
    def notify_compliance_alert(
        server_name: str,
        certname: str,
        issue: str,
    ) -> None:
        """Notification: Puppet compliance drift or failure detected."""
        try:
            NotificationService.create_sync(
                title="Compliance Alert",
                message=(
                    f"Server {server_name} ({certname}) has a compliance "
                    f"issue: {issue}"
                ),
                user_email="all",
                category="compliance",
                severity="warning",
                resource_type="server_request",
                resource_id=None,
                action_url=f"/servers?search={server_name}",
                icon="shield-alert",
                details={
                    "server_name": server_name,
                    "certname": certname,
                    "issue": issue,
                },
            )
        except Exception:
            logger.exception(
                "notify_compliance_alert failed for %s", server_name
            )
