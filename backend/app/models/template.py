"""SQLAlchemy model for server templates.

Templates pre-fill the server builder wizard with sensible defaults
for common server archetypes (web server, database, app server, etc.).
"""

from sqlalchemy import Boolean, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServerTemplate(Base):
    """A reusable server template that pre-fills the build wizard.

    Templates store default values for OS type, instance size, security
    profile, software packages, storage layout, and other configuration.
    Admins manage templates via the API; builders select them when
    creating new server requests.
    """

    __tablename__ = "server_templates"

    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'server'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    # Template defaults (pre-filled into the wizard)
    os_type: Mapped[str] = mapped_column(String(50), nullable=False)
    instance_size: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'us-east-1'")
    )
    security_profile: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'internal_only'")
    )
    puppet_role: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'base'")
    )
    domain_join: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    software_packages: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default=text("'[]'::jsonb")
    )
    additional_storage: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default=text("'[]'::jsonb")
    )
    default_tags: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default=text("'{}'::jsonb")
    )

    def __repr__(self) -> str:
        return (
            f"<ServerTemplate(id={self.id!r}, "
            f"name={self.name!r}, "
            f"os_type={self.os_type!r}, "
            f"is_active={self.is_active!r})>"
        )
