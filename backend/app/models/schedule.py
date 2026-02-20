"""SQLAlchemy models for scheduled builds.

Supports one-time and recurring server provisioning schedules.
Users can schedule a server build for a future date/time, or set up
recurring builds using cron expressions (e.g., spin up fresh dev
servers every Monday at 2 AM).

Each schedule stores the full server configuration as JSON so the
build can be replayed without any external dependencies.  Execution
history is tracked in a separate table for auditability.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class BuildSchedule(Base):
    """A schedule definition for automated server provisioning.

    Supports two schedule types:
    - ``one_time``: Runs once at the specified ``scheduled_at`` time.
    - ``recurring``: Runs on a cron-based schedule defined by
      ``cron_expression`` (standard 5-field cron syntax).

    The ``server_config`` column stores the full ServerCreateRequest
    payload as JSON so the build can be dispatched without needing to
    reference any other table.
    """

    __tablename__ = "build_schedules"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'active'"),
        index=True,
    )
    schedule_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )

    # Timing ------------------------------------------------------------------
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cron_expression: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    timezone: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'UTC'")
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # What to build -----------------------------------------------------------
    server_config: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )

    # Limits ------------------------------------------------------------------
    max_runs: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    run_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    # Who ---------------------------------------------------------------------
    created_by: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Relationships -----------------------------------------------------------
    executions: Mapped[list["ScheduleExecution"]] = relationship(
        "ScheduleExecution",
        back_populates="schedule",
        cascade="all, delete-orphan",
        order_by="ScheduleExecution.scheduled_for.desc()",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_build_schedules_next_run", "next_run_at"),
        Index("ix_build_schedules_status_next_run", "status", "next_run_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<BuildSchedule(id={self.id!r}, "
            f"name={self.name!r}, "
            f"schedule_type={self.schedule_type!r}, "
            f"status={self.status!r})>"
        )


class ScheduleExecution(Base):
    """A single execution record for a scheduled build.

    Every time a schedule fires (or is triggered manually via run-now),
    a ScheduleExecution row is created to track the outcome.  On
    success the ``server_request_id`` links to the ServerRequest that
    was created.
    """

    __tablename__ = "schedule_executions"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("build_schedules.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    server_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("server_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'pending'"),
        index=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # Relationships -----------------------------------------------------------
    schedule: Mapped["BuildSchedule"] = relationship(
        "BuildSchedule",
        back_populates="executions",
    )

    __table_args__ = (
        Index(
            "ix_schedule_executions_schedule_status",
            "schedule_id",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduleExecution(id={self.id!r}, "
            f"schedule_id={self.schedule_id!r}, "
            f"status={self.status!r}, "
            f"scheduled_for={self.scheduled_for!r})>"
        )
