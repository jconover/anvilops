"""
Maps AnvilOps server configurations to Puppet node classifications.

This module provides the classification logic that translates AnvilOps
server request parameters (puppet_role, environment, server_name) into
the Puppet Enterprise node classifier API payloads. It is consumed by
both the Celery enrollment tasks and the Puppet API endpoints.

Key responsibilities:
  - Resolve AnvilOps puppet_role values to Puppet role classes
  - Generate deterministic Puppet certnames from server names
  - Build PE node group configuration dicts for the classifier API
  - Produce a complete classification data bundle for a server request
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role-to-class mapping
# ---------------------------------------------------------------------------

# Maps AnvilOps puppet_role values (stored on ServerRequest) to the
# corresponding Puppet role class from our roles & profiles hierarchy.
ROLE_CLASS_MAP: dict[str, str] = {
    "base": "role::base",
    "web_server": "role::web_server",
    "db_server": "role::db_server",
    "app_server": "role::app_server",
    "dev_workstation": "role::dev_workstation",
}

# The PE "All Nodes" group UUID — used as the default parent for
# auto-created node groups.  This is a well-known constant in PE.
ALL_NODES_GROUP_ID = "00000000-0000-4000-8000-000000000000"

# Default internal domain for certname generation.
DEFAULT_DOMAIN = "anvilops.internal"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def get_role_class(puppet_role: str) -> str:
    """Resolve an AnvilOps puppet_role to a Puppet class name.

    Falls back to ``role::base`` for any unrecognised role value so that
    nodes always receive a valid classification.

    Args:
        puppet_role: The role key from the server request (e.g. ``"web_server"``).

    Returns:
        The fully qualified Puppet class name (e.g. ``"role::web_server"``).
    """
    role_class = ROLE_CLASS_MAP.get(puppet_role, "role::base")
    if puppet_role not in ROLE_CLASS_MAP:
        logger.warning(
            "Unknown puppet_role '%s', falling back to role::base",
            puppet_role,
        )
    return role_class


def get_certname(server_name: str, domain: str = DEFAULT_DOMAIN) -> str:
    """Generate the Puppet certname for a server.

    Convention: lowercase server name joined with the domain to produce
    a valid FQDN-style certname.  For example ``PROD-WEB-a3f8`` becomes
    ``prod-web-a3f8.anvilops.internal``.

    Args:
        server_name: The AnvilOps server name (e.g. ``"PROD-WEB-a3f8"``).
        domain: The internal DNS domain to append.

    Returns:
        The Puppet certname string.
    """
    return f"{server_name.lower()}.{domain}"


def build_node_group_config(puppet_role: str, environment: str) -> dict:
    """Build a PE node group configuration dict for the given role.

    The returned dict is compatible with the Puppet Enterprise classifier
    API ``POST /v1/groups`` payload.  Each AnvilOps role maps to a
    dedicated node group under the "All Nodes" parent group.

    Args:
        puppet_role: The AnvilOps puppet_role key.
        environment: The Puppet environment name (e.g. ``"production"``).

    Returns:
        A dict with keys: name, parent, environment, classes, description.
    """
    role_class = get_role_class(puppet_role)
    group_name = f"AnvilOps - {role_class}"

    return {
        "name": group_name,
        "parent": ALL_NODES_GROUP_ID,
        "environment": environment,
        "classes": {role_class: {}},
        "description": f"Auto-managed by AnvilOps for {puppet_role} servers",
    }


def get_node_classification_data(server_data: dict) -> dict:
    """Produce a complete Puppet classification bundle for a server request.

    This is the primary entry point used by both the enrollment Celery
    task and the Puppet API router.  It accepts a dict matching the shape
    returned by ``services.db.get_server_request`` and returns everything
    needed to classify the node in Puppet Enterprise.

    Args:
        server_data: Dict with at least ``puppet_role``, ``environment``,
            and ``server_name`` keys.  Missing keys fall back to safe
            defaults.

    Returns:
        Dict with keys: certname, role_class, environment,
        node_group_config.
    """
    puppet_role = server_data.get("puppet_role", "base")
    environment = server_data.get("environment", "production")
    server_name = server_data.get("server_name", "unknown")

    certname = get_certname(server_name)
    role_class = get_role_class(puppet_role)
    node_group_config = build_node_group_config(puppet_role, environment)

    logger.info(
        "Classification for %s: certname=%s, class=%s, env=%s",
        server_name,
        certname,
        role_class,
        environment,
    )

    return {
        "certname": certname,
        "role_class": role_class,
        "environment": environment,
        "node_group_config": node_group_config,
    }
