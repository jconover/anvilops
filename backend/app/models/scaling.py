"""SQLAlchemy models for Auto Scaling Group support."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScalingGroup(Base):
    """A managed group of identical servers with scaling policies.

    Stores the template configuration used to create new members and the
    scaling policy that governs automatic scale-up/scale-down behaviour.
    """

    __tablename__ = "scaling_groups"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'active'"),
        index=True,
    )

    # Template configuration -- describes what servers to create
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    os_type: Mapped[str] = mapped_column(String(50), nullable=False)
    instance_size: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str] = mapped_column(String(20), nullable=False)
    vpc_id: Mapped[str] = mapped_column(String(50), nullable=False)
    subnet_id: Mapped[str] = mapped_column(String(50), nullable=False)
    security_profile: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'internal_only'")
    )
    puppet_role: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'base'")
    )

    # Scaling configuration
    min_instances: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    max_instances: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("5")
    )
    desired_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    current_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    # Scaling policy
    scale_up_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("80")
    )
    scale_down_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("20")
    )
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("300")
    )

    last_scaled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    members: Mapped[list["ScalingGroupMember"]] = relationship(
        "ScalingGroupMember",
        back_populates="scaling_group",
        cascade="all, delete-orphan",
        order_by="ScalingGroupMember.member_index",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_scaling_groups_env_status", "environment", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ScalingGroup(id={self.id!r}, "
            f"name={self.name!r}, "
            f"status={self.status!r}, "
            f"current_count={self.current_count!r})>"
        )


class ScalingGroupMember(Base):
    """An individual server that belongs to a scaling group.

    Each member is linked to a ``ServerRequest`` that tracks its full
    provisioning lifecycle.  The ``member_index`` records the ordinal
    position within the group (used for deterministic naming).
    """

    __tablename__ = "scaling_group_members"

    scaling_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scaling_groups.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    server_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("server_requests.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    member_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'active'"),
    )

    # Relationships
    scaling_group: Mapped["ScalingGroup"] = relationship(
        "ScalingGroup",
        back_populates="members",
    )

    __table_args__ = (
        Index(
            "ix_scaling_group_members_group_index",
            "scaling_group_id",
            "member_index",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ScalingGroupMember(id={self.id!r}, "
            f"scaling_group_id={self.scaling_group_id!r}, "
            f"member_index={self.member_index!r}, "
            f"status={self.status!r})>"
        )
