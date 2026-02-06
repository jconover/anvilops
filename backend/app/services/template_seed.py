"""Seed the database with default server templates.

Call ``seed_default_templates(session)`` during application startup to
ensure the six standard templates exist.  The function is idempotent --
it only inserts templates whose names are not already present.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import ServerTemplate

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES: list[dict] = [
    {
        "name": "Standard Web Server",
        "description": (
            "Internal-facing web server on Amazon Linux 2023 with Nginx. "
            "Suitable for microservices, APIs, and internal web applications."
        ),
        "icon": "globe",
        "sort_order": 1,
        "os_type": "amazon_linux_2023",
        "instance_size": "small",
        "region": "us-east-1",
        "security_profile": "web_facing",
        "puppet_role": "web_server",
        "domain_join": False,
        "software_packages": ["nginx"],
        "additional_storage": [],
        "default_tags": {"tier": "web"},
    },
    {
        "name": "Public Web Server",
        "description": (
            "Internet-facing web server on Amazon Linux 2023 with Nginx and "
            "Certbot for TLS certificate management. Includes a larger "
            "instance size for handling public traffic."
        ),
        "icon": "globe-lock",
        "sort_order": 2,
        "os_type": "amazon_linux_2023",
        "instance_size": "medium",
        "region": "us-east-1",
        "security_profile": "web_facing",
        "puppet_role": "web_server",
        "domain_join": False,
        "software_packages": ["nginx", "certbot"],
        "additional_storage": [],
        "default_tags": {"tier": "web", "public": "true"},
    },
    {
        "name": "SQL Server",
        "description": (
            "Windows Server 2022 with Microsoft SQL Server. Pre-configured "
            "with dedicated D, E, and F drives for data, logs, and tempdb. "
            "Domain-joined for Active Directory authentication."
        ),
        "icon": "database",
        "sort_order": 3,
        "os_type": "windows_2022",
        "instance_size": "large",
        "region": "us-east-1",
        "security_profile": "database",
        "puppet_role": "db_server",
        "domain_join": True,
        "software_packages": ["sql-server-2022"],
        "additional_storage": [
            {"drive_letter": "D", "size_gb": 100, "volume_type": "gp3"},
            {"drive_letter": "E", "size_gb": 50, "volume_type": "gp3"},
            {"drive_letter": "F", "size_gb": 50, "volume_type": "gp3"},
        ],
        "default_tags": {"tier": "database"},
    },
    {
        "name": "App Server (.NET)",
        "description": (
            "Windows Server 2022 application server for .NET workloads. "
            "Pre-installed with the .NET SDK and domain-joined for "
            "enterprise integration."
        ),
        "icon": "cpu",
        "sort_order": 4,
        "os_type": "windows_2022",
        "instance_size": "medium",
        "region": "us-east-1",
        "security_profile": "internal_only",
        "puppet_role": "app_server",
        "domain_join": True,
        "software_packages": ["dotnet-sdk"],
        "additional_storage": [],
        "default_tags": {"tier": "application", "framework": "dotnet"},
    },
    {
        "name": "App Server (Java)",
        "description": (
            "Amazon Linux 2023 application server for Java workloads. "
            "Includes OpenJDK 17 and is sized for typical application "
            "server memory and CPU requirements."
        ),
        "icon": "coffee",
        "sort_order": 5,
        "os_type": "amazon_linux_2023",
        "instance_size": "medium",
        "region": "us-east-1",
        "security_profile": "internal_only",
        "puppet_role": "app_server",
        "domain_join": False,
        "software_packages": ["java-17"],
        "additional_storage": [],
        "default_tags": {"tier": "application", "framework": "java"},
    },
    {
        "name": "Dev Workstation",
        "description": (
            "Windows Server 2022 developer workstation with Git, VS Code, "
            "and Docker pre-installed. Ideal for remote development "
            "environments and CI/CD build agents."
        ),
        "icon": "monitor",
        "sort_order": 6,
        "os_type": "windows_2022",
        "instance_size": "medium",
        "region": "us-east-1",
        "security_profile": "internal_only",
        "puppet_role": "dev_workstation",
        "domain_join": False,
        "software_packages": ["git", "vscode", "docker"],
        "additional_storage": [],
        "default_tags": {"tier": "development"},
    },
]


async def seed_default_templates(session: AsyncSession) -> None:
    """Insert default server templates if they do not already exist.

    This function is idempotent.  Templates are matched by name --
    if a template with the same name already exists it is skipped.

    Args:
        session: An active async SQLAlchemy session.  The caller is
            responsible for committing the transaction.
    """
    # Fetch names of all existing templates in a single query
    result = await session.execute(
        select(ServerTemplate.name)
    )
    existing_names: set[str] = {row[0] for row in result.all()}

    created_count = 0
    for template_data in DEFAULT_TEMPLATES:
        if template_data["name"] in existing_names:
            logger.debug(
                "Template '%s' already exists, skipping", template_data["name"]
            )
            continue

        template = ServerTemplate(id=uuid.uuid4(), **template_data)
        session.add(template)
        created_count += 1
        logger.info("Seeding template: %s", template_data["name"])

    if created_count > 0:
        await session.flush()
        logger.info("Seeded %d default template(s)", created_count)
    else:
        logger.info("All default templates already exist, nothing to seed")
