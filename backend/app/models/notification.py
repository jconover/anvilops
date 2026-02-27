"""SQLAlchemy model for in-app notifications."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    """An in-app notification for a user.

    Notifications are created for build events (started, completed, failed),
    approval requests, compliance alerts, and system messages.  They can
    target a specific user (by email) or all users (user_email = "all").
    """

    __tablename__ = "notifications"

    user_email: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'system'"),
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'info'"),
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        index=True,
        server_default=text("false"),
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Link to related resource
    resource_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    action_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )

    # Metadata
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index(
            "ix_notifications_user_created",
            "user_email",
            "created_at",
        ),
        Index(
            "ix_notifications_user_unread",
            "user_email",
            "is_read",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id!r}, "
            f"user_email={self.user_email!r}, "
            f"category={self.category!r}, "
            f"is_read={self.is_read!r})>"
        )
