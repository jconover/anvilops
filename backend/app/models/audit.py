"""SQLAlchemy model for audit logs.

Tracks all significant actions in AnvilOps for compliance auditing
and troubleshooting. Every server build, approval, configuration change,
and authentication event is recorded here.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """An immutable record of a significant action within AnvilOps.

    Audit logs capture who did what, when, to which resource, and from
    where.  They are append-only -- rows are never updated or deleted
    during normal operation.
    """

    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        index=True,
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )

    # Actor information
    actor_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    actor_role: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )

    # Resource that was acted upon
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(36), nullable=True, index=True
    )
    resource_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Additional context
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # Outcome
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'success'")
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_audit_logs_category_action", "category", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_timestamp_desc", timestamp.desc()),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id!r}, "
            f"action={self.action!r}, "
            f"actor_email={self.actor_email!r}, "
            f"resource_id={self.resource_id!r}, "
            f"status={self.status!r})>"
        )
