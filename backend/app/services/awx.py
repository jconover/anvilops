"""
AWX (Ansible Tower) service layer.

Provides both async and synchronous clients for the AWX REST API. The async
client (AWXService) is suitable for FastAPI endpoints; the sync client
(AWXServiceSync) is used by Celery tasks.

Responsibilities:
  - Inventory and host management
  - Job template lookup and launch
  - Job polling and log retrieval
  - High-level configuration pipeline orchestration
"""

import json
import logging
import time

import httpx

from app.core.config import settings
from app.services.awx_exceptions import (
    AWXAuthError,
    AWXConnectionError,
    AWXError,
    AWXTimeoutError,
)

logger = logging.getLogger(__name__)

# AWX job statuses that indicate the job is no longer running.
TERMINAL_STATUSES = frozenset({"successful", "failed", "error", "canceled"})

# Default connection variables per OS family.
LINUX_CONNECTION_VARS = {
    "ansible_connection": "ssh",
    "ansible_port": 22,
    "ansible_user": "ec2-user",
}

WINDOWS_CONNECTION_VARS = {
    "ansible_connection": "winrm",
    "ansible_port": 5986,
    "ansible_winrm_transport": "ntlm",
    "ansible_winrm_server_cert_validation": "validate",
}


def _is_windows(os_type: str) -> bool:
    """Return True if the os_type string indicates a Windows server."""
    return "windows" in os_type.lower()


def _os_family(os_type: str) -> str:
    """Return 'windows' or 'linux' based on the os_type string."""
    return "windows" if _is_windows(os_type) else "linux"


# ---------------------------------------------------------------------------
# Async client (for FastAPI endpoints)
# ---------------------------------------------------------------------------


class AWXService:
    """Async client for the AWX (Ansible Tower) REST API.

    Uses ``httpx.AsyncClient`` with HTTP Basic authentication.
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.AWX_BASE_URL).rstrip("/")
        self._auth = httpx.BasicAuth(
            username=username or settings.AWX_USERNAME,
            password=password or settings.AWX_PASSWORD,
        )
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and return the shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=self._auth,
                timeout=self._timeout,
                headers={"Content-Type": "application/json"},
                verify=settings.AWX_VERIFY_SSL,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    # -- HTTP helpers -------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        accept: str = "application/json",
    ) -> httpx.Response:
        """Execute an HTTP request against AWX and handle common errors."""
        client = await self._get_client()
        try:
            response = await client.request(
                method,
                path,
                json=json_body,
                params=params,
                headers={"Accept": accept},
            )
        except httpx.ConnectError as exc:
            raise AWXConnectionError(
                f"Cannot connect to AWX at {self.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AWXConnectionError(
                f"Request to AWX timed out: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise AWXAuthError(
                f"AWX authentication failed ({response.status_code})",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        if response.status_code >= 400:
            raise AWXError(
                f"AWX API error: {method} {path} returned {response.status_code}",
                status_code=response.status_code,
                response_body=response.text[:1000],
            )

        return response

    async def _get(
        self, path: str, *, params: dict | None = None, accept: str = "application/json"
    ) -> httpx.Response:
        return await self._request("GET", path, params=params, accept=accept)

    async def _post(self, path: str, *, json_body: dict | None = None) -> httpx.Response:
        return await self._request("POST", path, json_body=json_body)

    async def _delete(self, path: str) -> httpx.Response:
        return await self._request("DELETE", path)

    # -- Public API ---------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if AWX is reachable and responding.

        GET /api/v2/ping/
        """
        try:
            response = await self._get("/api/v2/ping/")
            return response.status_code == 200
        except AWXError:
            return False

    async def add_host_to_inventory(
        self,
        inventory_id: int,
        hostname: str,
        ip_address: str,
        variables: dict,
    ) -> int:
        """Create a host inside an AWX inventory.

        POST /api/v2/hosts/

        Returns the newly created host ID.
        """
        host_vars = {**variables, "ansible_host": ip_address}
        body = {
            "name": hostname,
            "inventory": inventory_id,
            "variables": json.dumps(host_vars),
            "enabled": True,
        }
        logger.info(
            "Adding host %s (%s) to inventory %d",
            hostname, ip_address, inventory_id,
        )
        response = await self._post("/api/v2/hosts/", json_body=body)
        host_id: int = response.json()["id"]
        logger.info("Created AWX host id=%d for %s", host_id, hostname)
        return host_id

    async def add_host_to_group(self, group_id: int, host_id: int) -> None:
        """Associate an existing host with a group.

        POST /api/v2/groups/{group_id}/hosts/
        """
        logger.info("Adding host %d to group %d", host_id, group_id)
        await self._post(
            f"/api/v2/groups/{group_id}/hosts/",
            json_body={"id": host_id},
        )

    async def launch_job_template(
        self,
        template_id: int,
        extra_vars: dict | None = None,
        inventory: int | None = None,
        limit: str | None = None,
    ) -> int:
        """Launch an AWX job template and return the job ID.

        POST /api/v2/job_templates/{template_id}/launch/
        """
        body: dict = {}
        if extra_vars:
            body["extra_vars"] = json.dumps(extra_vars)
        if inventory is not None:
            body["inventory"] = inventory
        if limit is not None:
            body["limit"] = limit

        logger.info(
            "Launching job template %d (inventory=%s, limit=%s)",
            template_id, inventory, limit,
        )
        response = await self._post(
            f"/api/v2/job_templates/{template_id}/launch/",
            json_body=body,
        )
        job_id: int = response.json()["id"]
        logger.info("Launched AWX job %d from template %d", job_id, template_id)
        return job_id

    async def get_job_status(self, job_id: int) -> dict:
        """Retrieve the current status of an AWX job.

        GET /api/v2/jobs/{job_id}/

        Returns a normalized dict with id, status, failed, finished, and elapsed.
        """
        response = await self._get(f"/api/v2/jobs/{job_id}/")
        data = response.json()
        return {
            "id": data["id"],
            "status": data["status"],
            "failed": data.get("failed", False),
            "finished": data.get("finished"),
            "elapsed": data.get("elapsed", 0.0),
        }

    async def wait_for_job(
        self,
        job_id: int,
        poll_interval: int = 10,
        timeout: int = 600,
    ) -> dict:
        """Poll an AWX job until it reaches a terminal status.

        Raises AWXTimeoutError if the job does not complete within *timeout*
        seconds.
        """
        import asyncio

        logger.info(
            "Waiting for AWX job %d (poll=%ds, timeout=%ds)",
            job_id, poll_interval, timeout,
        )
        elapsed = 0
        current = "unknown"
        while elapsed < timeout:
            status = await self.get_job_status(job_id)
            current = status["status"]
            logger.debug("Job %d status: %s (elapsed %ds)", job_id, current, elapsed)

            if current in TERMINAL_STATUSES:
                logger.info(
                    "Job %d finished with status=%s in %.1fs",
                    job_id, current, status["elapsed"],
                )
                return status

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise AWXTimeoutError(
            f"AWX job {job_id} did not complete within {timeout}s (last status: {current})"
        )

    async def get_job_stdout(self, job_id: int) -> str:
        """Retrieve the plain-text stdout of an AWX job.

        GET /api/v2/jobs/{job_id}/stdout/?format=txt
        """
        response = await self._get(
            f"/api/v2/jobs/{job_id}/stdout/",
            params={"format": "txt"},
            accept="text/plain",
        )
        return response.text

    async def get_or_create_inventory(
        self, name: str, organization_id: int = 1
    ) -> int:
        """Return the ID of the named inventory, creating it if necessary.

        GET  /api/v2/inventories/?name={name}
        POST /api/v2/inventories/
        """
        response = await self._get(
            "/api/v2/inventories/",
            params={"name": name},
        )
        results = response.json().get("results", [])
        if results:
            inv_id: int = results[0]["id"]
            logger.debug("Found existing inventory %s (id=%d)", name, inv_id)
            return inv_id

        logger.info("Creating AWX inventory: %s", name)
        create_resp = await self._post(
            "/api/v2/inventories/",
            json_body={"name": name, "organization": organization_id},
        )
        inv_id = create_resp.json()["id"]
        logger.info("Created AWX inventory %s (id=%d)", name, inv_id)
        return inv_id

    async def get_or_create_group(
        self, inventory_id: int, group_name: str
    ) -> int:
        """Return the ID of the named group within an inventory, creating it if needed.

        GET  /api/v2/inventories/{inventory_id}/groups/?name={group_name}
        POST /api/v2/groups/
        """
        response = await self._get(
            f"/api/v2/inventories/{inventory_id}/groups/",
            params={"name": group_name},
        )
        results = response.json().get("results", [])
        if results:
            grp_id: int = results[0]["id"]
            logger.debug(
                "Found existing group %s in inventory %d (id=%d)",
                group_name, inventory_id, grp_id,
            )
            return grp_id

        logger.info(
            "Creating AWX group %s in inventory %d", group_name, inventory_id
        )
        create_resp = await self._post(
            "/api/v2/groups/",
            json_body={"name": group_name, "inventory": inventory_id},
        )
        grp_id = create_resp.json()["id"]
        logger.info("Created AWX group %s (id=%d)", group_name, grp_id)
        return grp_id

    async def get_job_template_by_name(self, name: str) -> int | None:
        """Look up a job template by exact name.

        GET /api/v2/job_templates/?name={name}

        Returns the template ID or None if not found.
        """
        response = await self._get(
            "/api/v2/job_templates/",
            params={"name": name},
        )
        results = response.json().get("results", [])
        if results:
            template_id: int = results[0]["id"]
            logger.debug("Resolved job template %s -> id=%d", name, template_id)
            return template_id

        logger.warning("Job template not found: %s", name)
        return None

    async def remove_host(self, host_id: int) -> None:
        """Delete a host from AWX.

        DELETE /api/v2/hosts/{host_id}/

        Used during decommission or rollback.
        """
        logger.info("Removing AWX host %d", host_id)
        await self._delete(f"/api/v2/hosts/{host_id}/")

    # -- High-level orchestration -------------------------------------------

    async def run_configuration_pipeline(self, server_data: dict) -> dict:
        """Run the full Day-1 configuration pipeline for a newly provisioned server.

        This is the main entry point called (via the sync wrapper) from Celery
        tasks after Terraform has created the EC2 instance.

        Args:
            server_data: Dict matching the shape returned by
                ``services.db.get_server_request``. Must include at minimum:
                server_name, environment, os_type, private_ip (or
                public_ip), domain_join, and software_packages.

        Returns:
            Dict with keys: success, jobs (list of per-template results),
            and host_id.
        """
        server_name: str = server_data["server_name"]
        environment: str = server_data["environment"]
        os_type: str = server_data["os_type"]
        ip_address: str = server_data.get("private_ip") or server_data.get("public_ip", "")
        domain_join: bool = server_data.get("domain_join", False)
        software_packages: list = server_data.get("software_packages") or []
        os_family = _os_family(os_type)

        logger.info(
            "Starting AWX configuration pipeline for %s (%s, %s, ip=%s)",
            server_name, environment, os_family, ip_address,
        )

        # 1. Get or create inventory: anvilops-{environment}
        inventory_name = f"anvilops-{environment}"
        inventory_id = await self.get_or_create_inventory(inventory_name)

        # 2. Get or create group for the OS family
        group_id = await self.get_or_create_group(inventory_id, os_family)

        # 3. Build host connection variables
        if os_family == "windows":
            connection_vars = {**WINDOWS_CONNECTION_VARS}
        else:
            connection_vars = {**LINUX_CONNECTION_VARS}

        # Include extra context that playbooks may find useful.
        connection_vars["anvilops_server_name"] = server_name
        connection_vars["anvilops_environment"] = environment
        connection_vars["anvilops_os_type"] = os_type
        connection_vars["anvilops_request_id"] = server_data.get("id", "")

        # 4. Add host to inventory and group
        host_id = await self.add_host_to_inventory(
            inventory_id=inventory_id,
            hostname=server_name,
            ip_address=ip_address,
            variables=connection_vars,
        )
        await self.add_host_to_group(group_id, host_id)

        # 5. Determine the ordered list of job templates to execute.
        template_names = self._resolve_template_names(
            os_family=os_family,
            domain_join=domain_join,
            software_packages=software_packages,
        )

        # 6. Sequentially launch and wait for each template.
        job_results: list[dict] = []
        pipeline_success = True

        for tpl_name in template_names:
            template_id = await self.get_job_template_by_name(tpl_name)
            if template_id is None:
                logger.error("Job template %s not found in AWX, skipping", tpl_name)
                job_results.append({
                    "template": tpl_name,
                    "job_id": None,
                    "status": "error",
                    "error": f"Job template '{tpl_name}' not found in AWX",
                })
                pipeline_success = False
                break

            extra_vars: dict = {
                "server_name": server_name,
                "os_type": os_type,
                "environment": environment,
            }
            if tpl_name == "anvilops-install-software" and software_packages:
                extra_vars["software_packages"] = software_packages

            job_id = await self.launch_job_template(
                template_id=template_id,
                extra_vars=extra_vars,
                inventory=inventory_id,
                limit=server_name,
            )

            try:
                final_status = await self.wait_for_job(job_id)
            except AWXTimeoutError as exc:
                logger.error("Job %d timed out for template %s", job_id, tpl_name)
                job_results.append({
                    "template": tpl_name,
                    "job_id": job_id,
                    "status": "timeout",
                    "error": str(exc),
                })
                pipeline_success = False
                break

            job_results.append({
                "template": tpl_name,
                "job_id": job_id,
                "status": final_status["status"],
            })

            if final_status["status"] != "successful":
                logger.error(
                    "Job %d (%s) finished with status %s, aborting pipeline",
                    job_id, tpl_name, final_status["status"],
                )
                pipeline_success = False
                break

            logger.info(
                "Job %d (%s) completed successfully in %.1fs",
                job_id, tpl_name, final_status["elapsed"],
            )

        result = {
            "success": pipeline_success,
            "jobs": job_results,
            "host_id": host_id,
        }
        logger.info(
            "AWX configuration pipeline %s for %s: %s",
            "succeeded" if pipeline_success else "failed",
            server_name,
            result,
        )
        return result

    @staticmethod
    def _resolve_template_names(
        os_family: str,
        domain_join: bool,
        software_packages: list,
    ) -> list[str]:
        """Return the ordered list of AWX job template names to execute.

        Template naming convention:
          - anvilops-{os_family}-base  (always first)
          - anvilops-domain-join       (if domain_join is True)
          - anvilops-install-software  (if software_packages is non-empty)
          - anvilops-deploy-agents     (always last)
        """
        templates = [f"anvilops-{os_family}-base"]
        if domain_join:
            templates.append("anvilops-domain-join")
        if software_packages:
            templates.append("anvilops-install-software")
        templates.append("anvilops-deploy-agents")
        return templates


# ---------------------------------------------------------------------------
# Synchronous client (for Celery tasks)
# ---------------------------------------------------------------------------


class AWXServiceSync:
    """Synchronous client for the AWX REST API.

    Uses ``httpx.Client`` (blocking) so it can be called directly from Celery
    workers without an event loop.
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.AWX_BASE_URL).rstrip("/")
        self._auth = httpx.BasicAuth(
            username=username or settings.AWX_USERNAME,
            password=password or settings.AWX_PASSWORD,
        )
        self._timeout = timeout
        self.client = httpx.Client(
            base_url=self.base_url,
            auth=self._auth,
            timeout=self._timeout,
            headers={"Content-Type": "application/json"},
            verify=settings.AWX_VERIFY_SSL,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    # -- HTTP helpers -------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        accept: str = "application/json",
    ) -> httpx.Response:
        """Execute a synchronous HTTP request against AWX."""
        try:
            response = self.client.request(
                method,
                path,
                json=json_body,
                params=params,
                headers={"Accept": accept},
            )
        except httpx.ConnectError as exc:
            raise AWXConnectionError(
                f"Cannot connect to AWX at {self.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise AWXConnectionError(
                f"Request to AWX timed out: {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise AWXAuthError(
                f"AWX authentication failed ({response.status_code})",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        if response.status_code >= 400:
            raise AWXError(
                f"AWX API error: {method} {path} returned {response.status_code}",
                status_code=response.status_code,
                response_body=response.text[:1000],
            )

        return response

    def _get(
        self, path: str, *, params: dict | None = None, accept: str = "application/json"
    ) -> httpx.Response:
        return self._request("GET", path, params=params, accept=accept)

    def _post(self, path: str, *, json_body: dict | None = None) -> httpx.Response:
        return self._request("POST", path, json_body=json_body)

    def _delete(self, path: str) -> httpx.Response:
        return self._request("DELETE", path)

    # -- Public API ---------------------------------------------------------

    def health_check(self) -> bool:
        """Return True if AWX is reachable.

        GET /api/v2/ping/
        """
        try:
            response = self._get("/api/v2/ping/")
            return response.status_code == 200
        except AWXError:
            return False

    def add_host_to_inventory(
        self,
        inventory_id: int,
        hostname: str,
        ip_address: str,
        variables: dict,
    ) -> int:
        """Create a host inside an AWX inventory. Returns the host ID.

        POST /api/v2/hosts/
        """
        host_vars = {**variables, "ansible_host": ip_address}
        body = {
            "name": hostname,
            "inventory": inventory_id,
            "variables": json.dumps(host_vars),
            "enabled": True,
        }
        logger.info(
            "Adding host %s (%s) to inventory %d",
            hostname, ip_address, inventory_id,
        )
        response = self._post("/api/v2/hosts/", json_body=body)
        host_id: int = response.json()["id"]
        logger.info("Created AWX host id=%d for %s", host_id, hostname)
        return host_id

    def add_host_to_group(self, group_id: int, host_id: int) -> None:
        """Associate a host with a group.

        POST /api/v2/groups/{group_id}/hosts/
        """
        logger.info("Adding host %d to group %d", host_id, group_id)
        self._post(
            f"/api/v2/groups/{group_id}/hosts/",
            json_body={"id": host_id},
        )

    def launch_job_template(
        self,
        template_id: int,
        extra_vars: dict | None = None,
        inventory: int | None = None,
        limit: str | None = None,
    ) -> int:
        """Launch a job template and return the job ID.

        POST /api/v2/job_templates/{template_id}/launch/
        """
        body: dict = {}
        if extra_vars:
            body["extra_vars"] = json.dumps(extra_vars)
        if inventory is not None:
            body["inventory"] = inventory
        if limit is not None:
            body["limit"] = limit

        logger.info(
            "Launching job template %d (inventory=%s, limit=%s)",
            template_id, inventory, limit,
        )
        response = self._post(
            f"/api/v2/job_templates/{template_id}/launch/",
            json_body=body,
        )
        job_id: int = response.json()["id"]
        logger.info("Launched AWX job %d from template %d", job_id, template_id)
        return job_id

    def get_job_status(self, job_id: int) -> dict:
        """Return a normalized status dict for the given job.

        GET /api/v2/jobs/{job_id}/
        """
        response = self._get(f"/api/v2/jobs/{job_id}/")
        data = response.json()
        return {
            "id": data["id"],
            "status": data["status"],
            "failed": data.get("failed", False),
            "finished": data.get("finished"),
            "elapsed": data.get("elapsed", 0.0),
        }

    def wait_for_job(
        self,
        job_id: int,
        poll_interval: int = 10,
        timeout: int = 600,
    ) -> dict:
        """Block until the AWX job reaches a terminal status.

        Raises AWXTimeoutError if the job does not finish within *timeout* seconds.
        """
        logger.info(
            "Waiting for AWX job %d (poll=%ds, timeout=%ds)",
            job_id, poll_interval, timeout,
        )
        elapsed = 0
        current = "unknown"
        while elapsed < timeout:
            status = self.get_job_status(job_id)
            current = status["status"]
            logger.debug("Job %d status: %s (elapsed %ds)", job_id, current, elapsed)

            if current in TERMINAL_STATUSES:
                logger.info(
                    "Job %d finished with status=%s in %.1fs",
                    job_id, current, status["elapsed"],
                )
                return status

            time.sleep(poll_interval)
            elapsed += poll_interval

        raise AWXTimeoutError(
            f"AWX job {job_id} did not complete within {timeout}s (last status: {current})"
        )

    def get_job_stdout(self, job_id: int) -> str:
        """Return the plain-text stdout of an AWX job.

        GET /api/v2/jobs/{job_id}/stdout/?format=txt
        """
        response = self._get(
            f"/api/v2/jobs/{job_id}/stdout/",
            params={"format": "txt"},
            accept="text/plain",
        )
        return response.text

    def get_or_create_inventory(self, name: str, organization_id: int = 1) -> int:
        """Return the inventory ID for *name*, creating it if it does not exist.

        GET  /api/v2/inventories/?name={name}
        POST /api/v2/inventories/
        """
        response = self._get("/api/v2/inventories/", params={"name": name})
        results = response.json().get("results", [])
        if results:
            inv_id: int = results[0]["id"]
            logger.debug("Found existing inventory %s (id=%d)", name, inv_id)
            return inv_id

        logger.info("Creating AWX inventory: %s", name)
        create_resp = self._post(
            "/api/v2/inventories/",
            json_body={"name": name, "organization": organization_id},
        )
        inv_id = create_resp.json()["id"]
        logger.info("Created AWX inventory %s (id=%d)", name, inv_id)
        return inv_id

    def get_or_create_group(self, inventory_id: int, group_name: str) -> int:
        """Return the group ID within an inventory, creating it if needed.

        GET  /api/v2/inventories/{inventory_id}/groups/?name={group_name}
        POST /api/v2/groups/
        """
        response = self._get(
            f"/api/v2/inventories/{inventory_id}/groups/",
            params={"name": group_name},
        )
        results = response.json().get("results", [])
        if results:
            grp_id: int = results[0]["id"]
            logger.debug(
                "Found existing group %s in inventory %d (id=%d)",
                group_name, inventory_id, grp_id,
            )
            return grp_id

        logger.info(
            "Creating AWX group %s in inventory %d", group_name, inventory_id
        )
        create_resp = self._post(
            "/api/v2/groups/",
            json_body={"name": group_name, "inventory": inventory_id},
        )
        grp_id = create_resp.json()["id"]
        logger.info("Created AWX group %s (id=%d)", group_name, grp_id)
        return grp_id

    def get_job_template_by_name(self, name: str) -> int | None:
        """Look up a job template by exact name. Returns ID or None.

        GET /api/v2/job_templates/?name={name}
        """
        response = self._get("/api/v2/job_templates/", params={"name": name})
        results = response.json().get("results", [])
        if results:
            template_id: int = results[0]["id"]
            logger.debug("Resolved job template %s -> id=%d", name, template_id)
            return template_id

        logger.warning("Job template not found: %s", name)
        return None

    def remove_host(self, host_id: int) -> None:
        """Delete a host from AWX inventory.

        DELETE /api/v2/hosts/{host_id}/
        """
        logger.info("Removing AWX host %d", host_id)
        self._delete(f"/api/v2/hosts/{host_id}/")

    # -- High-level orchestration -------------------------------------------

    def run_configuration_pipeline(self, server_data: dict) -> dict:
        """Run the full Day-1 AWX configuration pipeline synchronously.

        Intended to be called from Celery tasks after Terraform provisioning.

        Args:
            server_data: Dict matching services.db.get_server_request output.
                Must include: server_name, environment, os_type, and either
                private_ip or public_ip. Optionally: domain_join,
                software_packages.

        Returns:
            Dict with keys: success (bool), jobs (list), host_id (int).
        """
        server_name: str = server_data["server_name"]
        environment: str = server_data["environment"]
        os_type: str = server_data["os_type"]
        ip_address: str = server_data.get("private_ip") or server_data.get("public_ip", "")
        domain_join: bool = server_data.get("domain_join", False)
        software_packages: list = server_data.get("software_packages") or []
        os_family = _os_family(os_type)

        logger.info(
            "Starting AWX configuration pipeline for %s (%s, %s, ip=%s)",
            server_name, environment, os_family, ip_address,
        )

        # 1. Get or create inventory
        inventory_name = f"anvilops-{environment}"
        inventory_id = self.get_or_create_inventory(inventory_name)

        # 2. Get or create OS group
        group_id = self.get_or_create_group(inventory_id, os_family)

        # 3. Build host connection variables
        if os_family == "windows":
            connection_vars = {**WINDOWS_CONNECTION_VARS}
        else:
            connection_vars = {**LINUX_CONNECTION_VARS}

        connection_vars["anvilops_server_name"] = server_name
        connection_vars["anvilops_environment"] = environment
        connection_vars["anvilops_os_type"] = os_type
        connection_vars["anvilops_request_id"] = server_data.get("id", "")

        # 4. Add host to inventory and group
        host_id = self.add_host_to_inventory(
            inventory_id=inventory_id,
            hostname=server_name,
            ip_address=ip_address,
            variables=connection_vars,
        )
        self.add_host_to_group(group_id, host_id)

        # 5. Determine job templates
        template_names = AWXService._resolve_template_names(
            os_family=os_family,
            domain_join=domain_join,
            software_packages=software_packages,
        )

        # 6. Run each template sequentially
        job_results: list[dict] = []
        pipeline_success = True

        for tpl_name in template_names:
            template_id = self.get_job_template_by_name(tpl_name)
            if template_id is None:
                logger.error("Job template %s not found in AWX, aborting", tpl_name)
                job_results.append({
                    "template": tpl_name,
                    "job_id": None,
                    "status": "error",
                    "error": f"Job template '{tpl_name}' not found in AWX",
                })
                pipeline_success = False
                break

            extra_vars: dict = {
                "server_name": server_name,
                "os_type": os_type,
                "environment": environment,
            }
            if tpl_name == "anvilops-install-software" and software_packages:
                extra_vars["software_packages"] = software_packages

            job_id = self.launch_job_template(
                template_id=template_id,
                extra_vars=extra_vars,
                inventory=inventory_id,
                limit=server_name,
            )

            try:
                final_status = self.wait_for_job(job_id)
            except AWXTimeoutError as exc:
                logger.error("Job %d timed out for template %s", job_id, tpl_name)
                job_results.append({
                    "template": tpl_name,
                    "job_id": job_id,
                    "status": "timeout",
                    "error": str(exc),
                })
                pipeline_success = False
                break

            job_results.append({
                "template": tpl_name,
                "job_id": job_id,
                "status": final_status["status"],
            })

            if final_status["status"] != "successful":
                logger.error(
                    "Job %d (%s) finished with status %s, aborting pipeline",
                    job_id, tpl_name, final_status["status"],
                )
                pipeline_success = False
                break

            logger.info(
                "Job %d (%s) completed successfully in %.1fs",
                job_id, tpl_name, final_status["elapsed"],
            )

        result = {
            "success": pipeline_success,
            "jobs": job_results,
            "host_id": host_id,
        }
        logger.info(
            "AWX configuration pipeline %s for %s: %s",
            "succeeded" if pipeline_success else "failed",
            server_name,
            result,
        )
        return result
