"""SQLAlchemy models for drift detection and alerting.

Tracks individual drift events detected by PuppetDB report polling,
and drift alerts generated when patterns or thresholds are met.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DriftEvent(Base):
    """A single drift event detected on a managed server.

    Drift events are created when PuppetDB reports a corrective change
    (i.e. a resource was out of its desired state and Puppet corrected it)
    or when a failed resource indicates unresolved drift.

    Each event captures the specific resource, property, old/new values,
    severity classification, and whether the drift was auto-corrected.
    """

    __tablename__ = "drift_events"

    server_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("server_requests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    certname: Mapped[str] = mapped_column(
        String(255), index=True, nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Resource details
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    resource_title: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    property_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'medium'")
    )
    is_corrective: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_resolved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    resolution_type: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )

    # Categorisation
    drift_category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'configuration'")
    )
    cis_control_id: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )

    # Puppet report hash for deduplication
    report_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )

    # Relationships
    server_request: Mapped["ServerRequest"] = relationship(  # noqa: F821
        "ServerRequest",
        lazy="selectin",
    )
    alerts: Mapped[list["DriftAlert"]] = relationship(
        "DriftAlert",
        back_populates="drift_event",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index(
            "ix_drift_events_certname_detected",
            "certname",
            "detected_at",
        ),
        Index(
            "ix_drift_events_severity_resolved",
            "severity",
            "is_resolved",
        ),
        Index(
            "ix_drift_events_category",
            "drift_category",
        ),
        Index(
            "ix_drift_events_server_detected",
            "server_request_id",
            "detected_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DriftEvent(id={self.id!r}, "
            f"certname={self.certname!r}, "
            f"resource_type={self.resource_type!r}, "
            f"resource_title={self.resource_title!r}, "
            f"severity={self.severity!r}, "
            f"is_resolved={self.is_resolved!r})>"
        )


class DriftAlert(Base):
    """An alert generated from drift events or drift patterns.

    Alerts can be tied to a single drift event or represent aggregate
    conditions such as repeated drift on the same resource, multiple
    simultaneous drifts, or a compliance score dropping below a threshold.
    """

    __tablename__ = "drift_alerts"

    drift_event_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drift_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    server_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("server_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    alert_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'medium'")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    is_acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    acknowledged_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    drift_event: Mapped["DriftEvent" | None] = relationship(
        "DriftEvent",
        back_populates="alerts",
    )

    __table_args__ = (
        Index(
            "ix_drift_alerts_type_severity",
            "alert_type",
            "severity",
        ),
        Index(
            "ix_drift_alerts_unacknowledged",
            "is_acknowledged",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DriftAlert(id={self.id!r}, "
            f"alert_type={self.alert_type!r}, "
            f"severity={self.severity!r}, "
            f"is_acknowledged={self.is_acknowledged!r})>"
        )
