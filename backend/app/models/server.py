import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ServerRequest(Base):
    """A request to provision a new server.

    Tracks the full lifecycle from initial request through provisioning,
    configuration, validation, and eventual decommissioning.
    """

    __tablename__ = "server_requests"

    server_name: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, nullable=False
    )
    environment: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False
    )
    os_type: Mapped[str] = mapped_column(String(64), nullable=False)
    instance_size: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'us-east-1'")
    )
    vpc_id: Mapped[str] = mapped_column(String(64), nullable=False)
    subnet_id: Mapped[str] = mapped_column(String(64), nullable=False)
    security_profile: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'internal_only'")
    )
    domain_join: Mapped[bool] = mapped_column(
        nullable=False, server_default=text("false")
    )
    software_packages: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default=text("'[]'::jsonb")
    )
    additional_storage: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default=text("'[]'::jsonb")
    )
    tags: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default=text("'{}'::jsonb")
    )
    puppet_role: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'base'")
    )
    template_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        server_default=text("'pending'"),
    )
    status_message: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    aws_instance_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    private_ip: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    public_ip: Mapped[str | None] = mapped_column(
        String(45), nullable=True
    )
    dns_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    terraform_workspace: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    terraform_state_key: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )

    # AWX metadata (populated after configuration)
    awx_host_id: Mapped[int | None] = mapped_column(nullable=True)
    awx_inventory_id: Mapped[int | None] = mapped_column(nullable=True)
    awx_job_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Puppet metadata (populated after enrollment)
    puppet_certname: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )
    puppet_node_group_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    puppet_last_report_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    puppet_enrolled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ServiceNow CMDB metadata (populated after CMDB sync)
    cmdb_sys_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    # Port IDP metadata (populated after Port catalog sync)
    port_entity_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    build_steps: Mapped[list["BuildStep"]] = relationship(
        "BuildStep",
        back_populates="server_request",
        cascade="all, delete-orphan",
        order_by="BuildStep.step_order",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_server_requests_env_status", "environment", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<ServerRequest(id={self.id!r}, "
            f"server_name={self.server_name!r}, "
            f"environment={self.environment!r}, "
            f"status={self.status!r})>"
        )


class BuildStep(Base):
    """An individual step within a server build pipeline."""

    __tablename__ = "build_steps"

    server_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("server_requests.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    step_order: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'pending'"),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    output_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )

    server_request: Mapped["ServerRequest"] = relationship(
        "ServerRequest",
        back_populates="build_steps",
    )

    __table_args__ = (
        Index(
            "ix_build_steps_request_order",
            "server_request_id",
            "step_order",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<BuildStep(id={self.id!r}, "
            f"step_name={self.step_name!r}, "
            f"step_order={self.step_order!r}, "
            f"status={self.status!r})>"
        )
