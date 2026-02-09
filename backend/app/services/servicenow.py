"""ServiceNow CMDB integration service for AnvilOps.

Manages Configuration Items (CIs) in ServiceNow's CMDB via the
Table API. Syncs server lifecycle events: creation, configuration
changes, and retirement/decommission.

ServiceNow Table API: https://developer.servicenow.com/dev.do#!/reference/api/table

All operations are best-effort: errors are logged but never raised
so that CMDB sync failures cannot block the build pipeline.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OS type mapping: AnvilOps os_type -> ServiceNow display name
# ---------------------------------------------------------------------------
_OS_TYPE_MAP: dict[str, str] = {
    "windows_2022": "Windows Server 2022",
    "windows_2019": "Windows Server 2019",
    "amazon_linux_2023": "Amazon Linux 2023",
    "ubuntu_2204": "Ubuntu 22.04 LTS",
    "rhel_9": "Red Hat Enterprise Linux 9",
}

# ---------------------------------------------------------------------------
# Server status mapping: AnvilOps status -> (operational_status, install_status)
#
# ServiceNow operational_status values:
#   1 = Operational, 2 = Non-Operational, 3 = Repair in Progress,
#   4 = DR Standby, 5 = Ready, 6 = Retired
#
# ServiceNow install_status values:
#   1 = Installed, 2 = On Order, 3 = Received, 4 = In Maintenance,
#   5 = Pending Install, 6 = Pending Repair, 7 = Retired,
#   8 = Stolen, 9 = Absent
# ---------------------------------------------------------------------------
_STATUS_MAP: dict[str, tuple[int, int]] = {
    "pending": (2, 5),           # Non-Operational / Pending Install
    "approved": (2, 5),          # Non-Operational / Pending Install
    "building": (2, 5),          # Non-Operational / Pending Install
    "provisioning": (2, 5),      # Non-Operational / Pending Install
    "configuring": (2, 5),       # Non-Operational / Pending Install
    "validating": (2, 5),        # Non-Operational / Pending Install
    "ready": (1, 1),             # Operational / Installed
    "failed": (2, 6),            # Non-Operational / Pending Repair
    "decommissioning": (2, 4),   # Non-Operational / In Maintenance
    "decommissioned": (6, 7),    # Retired / Retired
}


class ServiceNowClient:
    """Sync server data with ServiceNow CMDB.

    Uses the ServiceNow Table API to create, update, query, and retire
    Configuration Items (CIs) in the ``cmdb_ci_server`` table.

    All public methods are best-effort: they log errors but never raise
    exceptions, returning ``None`` or empty results on failure.  This
    ensures the CMDB integration can never block or slow down the
    AnvilOps build pipeline.

    Parameters
    ----------
    instance_url:
        Full URL of the ServiceNow instance (e.g.
        ``https://dev12345.service-now.com``).
    username:
        ServiceNow integration user with Table API access.
    password:
        Password for the integration user.
    enabled:
        When ``False``, all API calls are short-circuited with a log
        message.  Allows disabling the integration without removing
        configuration.
    table:
        Target CMDB table name.  Defaults to ``cmdb_ci_server``.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        instance_url: str,
        username: str,
        password: str,
        enabled: bool = True,
        table: str = "cmdb_ci_server",
        timeout: float = 30.0,
    ):
        self.instance_url = instance_url.rstrip("/")
        self.username = username
        self.password = password
        self.enabled = enabled
        self.table = table
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_ci(self, server_data: dict) -> dict | None:
        """Create a new Configuration Item in CMDB.

        Maps AnvilOps server data to CMDB CI fields:
          - name            -> server_name
          - ip_address      -> private_ip
          - dns_domain      -> dns_name
          - os              -> os_type (mapped to ServiceNow OS names)
          - category        -> "Server"
          - subcategory     -> "Virtual"
          - environment     -> environment
          - operational_status -> based on server status
          - install_status  -> based on server status
          - assigned_to     -> requester (if present)
          - company         -> "AnvilOps"
          - u_puppet_certname    -> puppet_certname (custom field)
          - u_aws_instance_id    -> aws_instance_id (custom field)
          - u_aws_region         -> region (custom field)

        Parameters
        ----------
        server_data:
            Dict with AnvilOps server fields (as returned by
            ``app.services.db.get_server_request``).

        Returns
        -------
        dict or None
            ``{"sys_id": ..., "ci_number": ..., "result": ...}`` on
            success, ``None`` on failure or if the integration is
            disabled.
        """
        if not self._check_enabled("create_ci"):
            return None

        operational_status, install_status = self._map_status(
            server_data.get("status", "pending")
        )

        payload: dict[str, Any] = {
            "name": server_data.get("server_name", ""),
            "ip_address": server_data.get("private_ip", ""),
            "dns_domain": server_data.get("dns_name", ""),
            "os": self._map_os_type(server_data.get("os_type", "")),
            "category": "Server",
            "subcategory": "Virtual",
            "environment": self._map_environment(
                server_data.get("environment", "")
            ),
            "operational_status": str(operational_status),
            "install_status": str(install_status),
            "company": "AnvilOps",
            "short_description": (
                f"AnvilOps managed server: "
                f"{server_data.get('server_name', 'unknown')}"
            ),
            "u_puppet_certname": server_data.get("puppet_certname", ""),
            "u_aws_instance_id": server_data.get("aws_instance_id", ""),
            "u_aws_region": server_data.get("region", ""),
        }

        # Only set assigned_to if we have a requester value
        requester = server_data.get("requester")
        if requester:
            payload["assigned_to"] = requester

        result = self._request("POST", f"/api/now/table/{self.table}", data=payload)
        if result is None:
            return None

        record = result.get("result", {})
        sys_id = record.get("sys_id", "")
        ci_number = record.get("asset_tag", "") or record.get("sys_id", "")

        logger.info(
            "Created CMDB CI for %s: sys_id=%s",
            server_data.get("server_name", "unknown"),
            sys_id,
        )

        return {
            "sys_id": sys_id,
            "ci_number": ci_number,
            "result": record,
        }

    def update_ci(self, sys_id: str, updates: dict) -> dict | None:
        """Update an existing CI with new data.

        Parameters
        ----------
        sys_id:
            The ServiceNow ``sys_id`` of the CI to update.
        updates:
            Dict of CMDB field names to new values.  Only provided
            fields are updated; other fields are left unchanged.

        Returns
        -------
        dict or None
            ``{"sys_id": ..., "result": ...}`` on success, ``None`` on
            failure.
        """
        if not self._check_enabled("update_ci"):
            return None

        if not sys_id:
            logger.warning("update_ci called with empty sys_id, skipping")
            return None

        result = self._request(
            "PATCH",
            f"/api/now/table/{self.table}/{sys_id}",
            data=updates,
        )
        if result is None:
            return None

        record = result.get("result", {})
        logger.info("Updated CMDB CI sys_id=%s", sys_id)

        return {
            "sys_id": sys_id,
            "result": record,
        }

    def retire_ci(self, sys_id: str) -> dict | None:
        """Mark a CI as retired/decommissioned.

        Sets ``operational_status`` to ``6`` (Retired) and
        ``install_status`` to ``7`` (Retired).

        Parameters
        ----------
        sys_id:
            The ServiceNow ``sys_id`` of the CI to retire.

        Returns
        -------
        dict or None
            ``{"sys_id": ..., "result": ...}`` on success, ``None`` on
            failure.
        """
        if not self._check_enabled("retire_ci"):
            return None

        if not sys_id:
            logger.warning("retire_ci called with empty sys_id, skipping")
            return None

        updates = {
            "operational_status": "6",   # Retired
            "install_status": "7",       # Retired
            "short_description": "Decommissioned by AnvilOps",
        }

        result = self._request(
            "PATCH",
            f"/api/now/table/{self.table}/{sys_id}",
            data=updates,
        )
        if result is None:
            return None

        record = result.get("result", {})
        logger.info("Retired CMDB CI sys_id=%s", sys_id)

        return {
            "sys_id": sys_id,
            "result": record,
        }

    def get_ci(self, sys_id: str) -> dict | None:
        """Fetch a CI by sys_id.

        Parameters
        ----------
        sys_id:
            The ServiceNow ``sys_id`` of the CI.

        Returns
        -------
        dict or None
            The CI record dict, or ``None`` if not found / on error.
        """
        if not self._check_enabled("get_ci"):
            return None

        if not sys_id:
            logger.warning("get_ci called with empty sys_id, skipping")
            return None

        result = self._request("GET", f"/api/now/table/{self.table}/{sys_id}")
        if result is None:
            return None

        return result.get("result")

    def find_ci_by_name(self, server_name: str) -> dict | None:
        """Search CMDB for a CI by server name.

        Uses the ServiceNow ``sysparm_query`` parameter to filter by
        the ``name`` field.

        Parameters
        ----------
        server_name:
            The AnvilOps server name to search for.

        Returns
        -------
        dict or None
            The first matching CI record, or ``None`` if not found / on
            error.
        """
        if not self._check_enabled("find_ci_by_name"):
            return None

        if not server_name:
            logger.warning(
                "find_ci_by_name called with empty server_name, skipping"
            )
            return None

        result = self._request(
            "GET",
            f"/api/now/table/{self.table}",
            params={
                "sysparm_query": f"name={server_name}",
                "sysparm_limit": "1",
            },
        )
        if result is None:
            return None

        records = result.get("result", [])
        if not records:
            logger.debug("No CMDB CI found for server_name=%s", server_name)
            return None

        return records[0]

    def get_ci_relationships(self, sys_id: str) -> list[dict]:
        """Get CI relationships (depends on, used by, etc.).

        Queries the ``cmdb_rel_ci`` table for all relationships where
        the given CI is either the parent or child.

        Parameters
        ----------
        sys_id:
            The ServiceNow ``sys_id`` of the CI.

        Returns
        -------
        list[dict]
            List of relationship records, or empty list on failure.
        """
        if not self._check_enabled("get_ci_relationships"):
            return []

        if not sys_id:
            logger.warning(
                "get_ci_relationships called with empty sys_id, skipping"
            )
            return []

        result = self._request(
            "GET",
            "/api/now/table/cmdb_rel_ci",
            params={
                "sysparm_query": f"parent={sys_id}^ORchild={sys_id}",
                "sysparm_limit": "100",
            },
        )
        if result is None:
            return []

        return result.get("result", [])

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _map_os_type(self, os_type: str) -> str:
        """Map AnvilOps OS type to ServiceNow OS name.

        Falls back to the raw os_type string if no mapping is found.
        """
        return _OS_TYPE_MAP.get(os_type, os_type)

    def _map_status(self, server_status: str) -> tuple[int, int]:
        """Map server status to (operational_status, install_status).

        Returns ServiceNow integer codes for both fields.  Falls back
        to (2, 5) (Non-Operational / Pending Install) for unknown
        statuses.
        """
        return _STATUS_MAP.get(server_status, (2, 5))

    @staticmethod
    def _map_environment(environment: str) -> str:
        """Map AnvilOps environment name to ServiceNow environment.

        ServiceNow typically uses "Development", "Test", "Stage",
        "Production" as environment values.
        """
        mapping = {
            "dev": "Development",
            "staging": "Stage",
            "production": "Production",
        }
        return mapping.get(environment, environment)

    # ------------------------------------------------------------------
    # HTTP transport
    # ------------------------------------------------------------------

    def _check_enabled(self, method_name: str) -> bool:
        """Return True if the integration is enabled and configured."""
        if not self.enabled:
            logger.debug(
                "ServiceNow integration disabled, skipping %s", method_name
            )
            return False

        if not self.instance_url or not self.username:
            logger.warning(
                "ServiceNow not configured (missing instance_url or username), "
                "skipping %s",
                method_name,
            )
            return False

        return True

    def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict | None:
        """Make an authenticated request to the ServiceNow Table API.

        Uses HTTP Basic Auth and JSON content type.  All errors are
        caught and logged; the method returns ``None`` on any failure
        so that callers can treat CMDB operations as best-effort.

        Parameters
        ----------
        method:
            HTTP method (GET, POST, PATCH, DELETE).
        endpoint:
            API endpoint path (e.g. ``/api/now/table/cmdb_ci_server``).
        data:
            JSON body for POST/PATCH requests.
        params:
            Query parameters for GET requests.

        Returns
        -------
        dict or None
            Parsed JSON response on success, ``None`` on failure.
        """
        url = f"{self.instance_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    auth=(self.username, self.password),
                    json=data,
                    params=params,
                )

            if response.status_code >= 400:
                logger.error(
                    "ServiceNow API error: %s %s -> HTTP %d: %s",
                    method,
                    endpoint,
                    response.status_code,
                    response.text[:500],
                )
                return None

            return response.json()

        except httpx.TimeoutException:
            logger.warning(
                "ServiceNow API timeout: %s %s (%.1fs)",
                method,
                endpoint,
                self.timeout,
            )
            return None
        except httpx.HTTPError as exc:
            logger.warning(
                "ServiceNow API HTTP error: %s %s -> %s",
                method,
                endpoint,
                exc,
            )
            return None
        except Exception as exc:
            logger.exception(
                "Unexpected error calling ServiceNow API: %s %s -> %s",
                method,
                endpoint,
                exc,
            )
            return None


def get_servicenow_client() -> ServiceNowClient:
    """Create a ServiceNowClient from application settings.

    This is the standard way to obtain a client instance throughout
    the application.  It reads from ``app.core.config.settings`` on
    every call so that runtime configuration changes are picked up.
    """
    from app.core.config import settings

    return ServiceNowClient(
        instance_url=settings.SERVICENOW_INSTANCE_URL,
        username=settings.SERVICENOW_USERNAME,
        password=settings.SERVICENOW_PASSWORD,
        enabled=settings.SERVICENOW_ENABLED,
        table=settings.SERVICENOW_TABLE,
    )
