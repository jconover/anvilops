"""Pydantic schemas for Port IDP blueprint entity sync and webhooks."""

from datetime import datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Blueprint ID constants
# ---------------------------------------------------------------------------

PORT_BLUEPRINT_SERVER = "anvilops_server"
PORT_BLUEPRINT_TEMPLATE = "anvilops_server_template"
PORT_BLUEPRINT_SCALING_GROUP = "anvilops_scaling_group"

# ---------------------------------------------------------------------------
# Server blueprint entity
# ---------------------------------------------------------------------------


class PortServerEntity(BaseModel):
    """Port entity schema for the anvilops_server blueprint."""

    server_name: str = Field(..., description="Unique server hostname")
    environment: str = Field(..., description="Deployment environment (dev/staging/production)")
    os_type: str = Field(..., description="Operating system type")
    instance_size: str = Field(..., description="EC2 instance size tier")
    region: str = Field(..., description="AWS region")
    status: str = Field(..., description="Current server lifecycle status")
    private_ip: str | None = Field(None, description="Private IPv4 address")
    public_ip: str | None = Field(None, description="Public IPv4 address (if assigned)")
    dns_name: str | None = Field(None, description="DNS hostname")
    aws_instance_id: str | None = Field(None, description="EC2 instance ID")
    puppet_certname: str | None = Field(None, description="Puppet certificate name")
    puppet_environment: str | None = Field(None, description="Puppet environment branch")
    requester: str | None = Field(None, description="User who requested the server")
    cost_estimate_monthly: float | None = Field(
        None, description="Estimated monthly cost in USD"
    )
    created_at: datetime | None = Field(None, description="Server creation timestamp")
    updated_at: datetime | None = Field(None, description="Last modification timestamp")

    # Relation target identifier (the template this server was built from)
    server_template: str | None = Field(
        None, description="Identifier of the related ServerTemplate entity"
    )


# ---------------------------------------------------------------------------
# ServerTemplate blueprint entity
# ---------------------------------------------------------------------------


class PortServerTemplateEntity(BaseModel):
    """Port entity schema for the anvilops_server_template blueprint."""

    template_name: str = Field(..., description="Unique template name")
    os_type: str = Field(..., description="Operating system type")
    instance_size: str = Field(..., description="EC2 instance size tier")
    description: str | None = Field(None, description="Human-readable template description")
    default_region: str | None = Field(None, description="Default AWS region")
    base_ami_id: str | None = Field(None, description="Base AMI used by this template")
    puppet_role: str | None = Field(None, description="Puppet role applied to servers")
    software_packages: list[str] = Field(
        default_factory=list, description="Pre-installed software packages"
    )
    is_active: bool = Field(True, description="Whether this template is available for use")


# ---------------------------------------------------------------------------
# ScalingGroup blueprint entity
# ---------------------------------------------------------------------------


class PortScalingGroupEntity(BaseModel):
    """Port entity schema for the anvilops_scaling_group blueprint."""

    group_name: str = Field(..., description="Scaling group name")
    environment: str = Field(..., description="Deployment environment")
    min_count: int = Field(..., ge=0, description="Minimum instance count")
    max_count: int = Field(..., ge=1, description="Maximum instance count")
    current_count: int = Field(..., ge=0, description="Current running instance count")
    template_id: str | None = Field(
        None, description="AnvilOps template ID used for new instances"
    )
    status: str = Field(..., description="Scaling group lifecycle status")
    scaling_policy: str | None = Field(
        None, description="Active scaling policy name or description"
    )
    last_scaled_at: datetime | None = Field(
        None, description="Timestamp of the last scale event"
    )


# ---------------------------------------------------------------------------
# Webhook / self-service action schemas
# ---------------------------------------------------------------------------


class PortWebhookPayload(BaseModel):
    """Incoming webhook payload from Port."""

    action: str = Field(..., description="Action name triggered in Port")
    blueprint: str = Field(..., description="Blueprint identifier the action belongs to")
    entity_identifier: str | None = Field(
        None, description="Identifier of the entity the action targets (if any)"
    )
    properties: dict = Field(
        default_factory=dict, description="Key/value properties from the Port form"
    )
    triggered_by: str | None = Field(
        None, description="Email or identifier of the user who triggered the action"
    )


class PortSelfServiceAction(BaseModel):
    """Self-service action payload received from Port runner."""

    action_id: str = Field(..., description="Unique Port action run ID")
    blueprint_id: str = Field(..., description="Blueprint the action is defined on")
    entity_id: str | None = Field(
        None, description="Entity identifier the action targets (None for create actions)"
    )
    properties: dict = Field(
        default_factory=dict, description="User-supplied action input properties"
    )
    user_email: str | None = Field(
        None, description="Email of the Port user who invoked the action"
    )


# ---------------------------------------------------------------------------
# Helper functions: map AnvilOps data -> Port entity format
# ---------------------------------------------------------------------------


def server_to_port_entity(server_data: dict) -> dict:
    """Convert an AnvilOps server dict to a Port entity payload.

    Returns a dict matching Port's ``{ identifier, title, properties, relations }``
    structure for the ``anvilops_server`` blueprint.
    """
    identifier = server_data.get("server_name") or str(server_data.get("id", ""))
    title = server_data.get("server_name", identifier)

    properties: dict = {
        "server_name": server_data.get("server_name"),
        "environment": server_data.get("environment"),
        "os_type": server_data.get("os_type"),
        "instance_size": server_data.get("instance_size"),
        "region": server_data.get("region"),
        "status": server_data.get("status"),
        "private_ip": server_data.get("private_ip"),
        "public_ip": server_data.get("public_ip"),
        "dns_name": server_data.get("dns_name"),
        "aws_instance_id": server_data.get("aws_instance_id"),
        "puppet_certname": server_data.get("puppet_certname"),
        "puppet_environment": server_data.get("puppet_environment"),
        "requester": server_data.get("requester"),
        "cost_estimate_monthly": server_data.get("cost_estimate_monthly"),
        "created_at": (
            server_data["created_at"].isoformat()
            if isinstance(server_data.get("created_at"), datetime)
            else server_data.get("created_at")
        ),
        "updated_at": (
            server_data["updated_at"].isoformat()
            if isinstance(server_data.get("updated_at"), datetime)
            else server_data.get("updated_at")
        ),
    }
    # Strip None values so Port does not overwrite existing data with nulls
    properties = {k: v for k, v in properties.items() if v is not None}

    relations: dict = {}
    template_id = server_data.get("template_id") or server_data.get("server_template")
    if template_id:
        relations["server_template"] = str(template_id)

    return {
        "identifier": identifier,
        "title": title,
        "blueprint": PORT_BLUEPRINT_SERVER,
        "properties": properties,
        "relations": relations,
    }


def template_to_port_entity(template_data: dict) -> dict:
    """Convert an AnvilOps server template dict to a Port entity payload.

    Returns a dict matching Port's ``{ identifier, title, properties, relations }``
    structure for the ``anvilops_server_template`` blueprint.
    """
    identifier = template_data.get("name") or str(template_data.get("id", ""))
    title = template_data.get("name", identifier)

    properties: dict = {
        "template_name": template_data.get("name"),
        "os_type": template_data.get("os_type"),
        "instance_size": template_data.get("instance_size"),
        "description": template_data.get("description"),
        "default_region": template_data.get("default_region") or template_data.get("region"),
        "base_ami_id": template_data.get("base_ami_id"),
        "puppet_role": template_data.get("puppet_role"),
        "software_packages": template_data.get("software_packages", []),
        "is_active": template_data.get("is_active", True),
    }
    # Strip None values; keep False and empty lists intentionally
    properties = {k: v for k, v in properties.items() if v is not None}

    return {
        "identifier": identifier,
        "title": title,
        "blueprint": PORT_BLUEPRINT_TEMPLATE,
        "properties": properties,
        "relations": {},
    }
