"""
Puppet Enterprise service layer.

Provides both async and synchronous clients for the Puppet Enterprise REST
APIs.  The async client (PuppetEnterpriseService) is suitable for FastAPI
endpoints; the sync client (PuppetEnterpriseServiceSync) is used by Celery
tasks.

Puppet Enterprise exposes several APIs on different ports:
  - Node Classifier (NC) API  -- port 4433  -- /classifier-api/v1/
  - PuppetDB API               -- port 8081  -- /pdb/query/v4/
  - Orchestrator API            -- port 8143  -- /orchestrator/v1/
  - RBAC API                    -- port 4433  -- /rbac-api/v1/
  - Puppet CA API               -- port 8140  -- /puppet-ca/v1/
  - PuppetDB Command API        -- port 8081  -- /pdb/cmd/v1

Authentication is via a PE RBAC token passed in the ``X-Authentication``
header on every request.

Responsibilities:
  - Node classification (group management, node pinning)
  - PuppetDB queries (facts, reports, node status)
  - Certificate lifecycle (sign, revoke, clean)
  - Orchestrator integration (on-demand Puppet runs)
  - High-level enrollment pipeline for newly provisioned servers
  - Node purge for decommission workflows
"""

import logging
import time
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.services.puppet_exceptions import (
    PuppetAuthError,
    PuppetClassificationError,
    PuppetConnectionError,
    PuppetError,
    PuppetTimeoutError,
)

logger = logging.getLogger(__name__)


def _build_url(base_url: str, port: int, path: str) -> str:
    """Build a full URL from a base hostname/URL, port, and path.

    Puppet Enterprise APIs live on different ports on the same host.
    For example, given base_url="https://puppet.anvilops.internal",
    port=4433, path="/classifier-api/v1/groups" the result is:
        https://puppet.anvilops.internal:4433/classifier-api/v1/groups
    """
    # Strip any existing port from the base URL so we can substitute.
    # E.g. "https://puppet:8140" -> "https://puppet"
    from urllib.parse import urlparse

    parsed = urlparse(base_url)
    # Reconstruct with the desired port and no path (path comes from arg).
    netloc = parsed.hostname or parsed.netloc
    scheme = parsed.scheme or "https"
    base = f"{scheme}://{netloc}:{port}"
    return f"{base}{path}"


# ---------------------------------------------------------------------------
# Async client (for FastAPI endpoints)
# ---------------------------------------------------------------------------


class PuppetEnterpriseService:
    """Async client for the Puppet Enterprise REST APIs.

    Uses ``httpx.AsyncClient`` with PE RBAC token authentication.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        verify_ssl: bool | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.PUPPET_BASE_URL).rstrip("/")
        self.token = token or settings.PUPPET_API_TOKEN
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.PUPPET_VERIFY_SSL
        self._timeout = timeout
        self._headers = {
            "X-Authentication": self.token,
            "Content-Type": "application/json",
        }

        # Port configuration
        self._ca_port: int = settings.PUPPET_CA_PORT
        self._classifier_port: int = settings.PUPPET_CLASSIFIER_PORT
        self._puppetdb_port: int = settings.PUPPET_PUPPETDB_PORT
        self._orchestrator_port: int = settings.PUPPET_ORCHESTRATOR_PORT

        # Polling defaults
        self._checkin_timeout: int = settings.PUPPET_NODE_CHECKIN_TIMEOUT
        self._checkin_poll: int = settings.PUPPET_NODE_CHECKIN_POLL
        self._default_environment: str = settings.PUPPET_DEFAULT_ENVIRONMENT

        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create and return the shared async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                verify=self.verify_ssl,
                timeout=self._timeout,
                headers=self._headers,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()

    # -- URL builders -------------------------------------------------------

    def _classifier_url(self, path: str) -> str:
        """Build a full URL for the Node Classifier API."""
        return _build_url(self.base_url, self._classifier_port, f"/classifier-api/v1{path}")

    def _puppetdb_url(self, path: str) -> str:
        """Build a full URL for the PuppetDB API."""
        return _build_url(self.base_url, self._puppetdb_port, f"/pdb/query/v4{path}")

    def _puppetdb_cmd_url(self, path: str) -> str:
        """Build a full URL for the PuppetDB Command API."""
        return _build_url(self.base_url, self._puppetdb_port, f"/pdb/cmd/v1{path}")

    def _orchestrator_url(self, path: str) -> str:
        """Build a full URL for the Orchestrator API."""
        return _build_url(self.base_url, self._orchestrator_port, f"/orchestrator/v1{path}")

    def _ca_url(self, path: str) -> str:
        """Build a full URL for the Puppet CA API."""
        return _build_url(self.base_url, self._ca_port, f"/puppet-ca/v1{path}")

    # -- HTTP helpers -------------------------------------------------------

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | list | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Execute an HTTP request against a PE API and handle common errors."""
        client = await self._get_client()
        try:
            response = await client.request(
                method,
                url,
                json=json_body,
                params=params,
            )
        except httpx.ConnectError as exc:
            raise PuppetConnectionError(
                f"Cannot connect to Puppet Enterprise at {url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise PuppetConnectionError(
                f"Request to Puppet Enterprise timed out ({url}): {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise PuppetAuthError(
                f"Puppet Enterprise authentication failed ({response.status_code}) for {url}",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        if response.status_code >= 400:
            raise PuppetError(
                f"Puppet Enterprise API error: {method} {url} returned {response.status_code}",
                status_code=response.status_code,
                response_body=response.text[:1000],
            )

        return response

    async def _get(self, url: str, *, params: dict | None = None) -> httpx.Response:
        return await self._request("GET", url, params=params)

    async def _post(
        self, url: str, *, json_body: dict | list | None = None
    ) -> httpx.Response:
        return await self._request("POST", url, json_body=json_body)

    async def _put(
        self, url: str, *, json_body: dict | list | None = None
    ) -> httpx.Response:
        return await self._request("PUT", url, json_body=json_body)

    async def _delete(self, url: str) -> httpx.Response:
        return await self._request("DELETE", url)

    # -- Public API: Health -------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if PuppetDB is reachable and responding.

        GET /pdb/query/v4/version
        """
        try:
            url = self._puppetdb_url("/version")
            response = await self._get(url)
            return response.status_code == 200
        except PuppetError:
            return False

    # -- Public API: Node Classifier ----------------------------------------

    async def get_node_groups(self) -> list[dict]:
        """Return all node groups from the Node Classifier.

        GET /classifier-api/v1/groups
        """
        url = self._classifier_url("/groups")
        response = await self._get(url)
        return response.json()

    async def find_node_group_by_name(self, name: str) -> dict | None:
        """Search for a node group by exact name.

        Iterates through all groups returned by get_node_groups() and
        returns the first match, or None if not found.
        """
        groups = await self.get_node_groups()
        for group in groups:
            if group.get("name") == name:
                return group
        return None

    async def get_or_create_node_group(
        self,
        name: str,
        parent_id: str,
        environment: str,
        classes: dict,
        rule: list | None = None,
    ) -> str:
        """Return the ID of the named node group, creating it if necessary.

        GET  /classifier-api/v1/groups  (search for existing)
        POST /classifier-api/v1/groups  (create if missing)

        Args:
            name: Display name for the node group.
            parent_id: UUID of the parent group (e.g. the "All Nodes" group).
            environment: Puppet environment to assign (e.g. "production").
            classes: Dict of Puppet classes to include, e.g.
                     {"role::web_server": {}} or {"role::db_server": {"port": 5432}}.
            rule: Optional classification rule in NC rule format. For example:
                  ["or", ["=", "name", "some-certname"]].

        Returns:
            The UUID string of the (existing or newly created) node group.
        """
        existing = await self.find_node_group_by_name(name)
        if existing:
            group_id = existing["id"]
            logger.debug("Found existing node group %s (id=%s)", name, group_id)
            return group_id

        logger.info("Creating node group: %s (parent=%s, env=%s)", name, parent_id, environment)
        body: dict = {
            "name": name,
            "parent": parent_id,
            "environment": environment,
            "classes": classes,
        }
        if rule is not None:
            body["rule"] = rule

        url = self._classifier_url("/groups")
        response = await self._post(url, json_body=body)

        # The NC API returns the created group with its id, or the Location
        # header contains the URL to the new group.
        if response.status_code == 303:
            # Redirect response -- extract group ID from Location header.
            location = response.headers.get("location", "")
            group_id = location.rstrip("/").rsplit("/", 1)[-1]
        else:
            data = response.json()
            group_id = data.get("id", "")

        if not group_id:
            raise PuppetClassificationError(
                f"Failed to extract group ID after creating node group '{name}'",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        logger.info("Created node group %s (id=%s)", name, group_id)
        return group_id

    async def classify_node(
        self,
        certname: str,
        node_group_id: str,
        environment: str = "production",
    ) -> dict:
        """Pin a node to a node group in the Node Classifier.

        POST /classifier-api/v1/groups/{node_group_id}/pin

        This assigns the node (by certname) to the specified group so that
        it receives the classes defined in that group.

        Args:
            certname: The Puppet agent certificate name of the node.
            node_group_id: UUID of the target node group.
            environment: Puppet environment (informational; the group's
                         environment takes precedence).

        Returns:
            The response body from the classifier API.
        """
        url = self._classifier_url(f"/groups/{node_group_id}/pin")
        body = {"nodes": [certname]}
        logger.info(
            "Pinning node %s to group %s (env=%s)",
            certname, node_group_id, environment,
        )
        response = await self._post(url, json_body=body)

        # Pin endpoint may return 204 No Content on success.
        if response.status_code == 204 or not response.text.strip():
            result = {"certname": certname, "node_group_id": node_group_id, "pinned": True}
        else:
            result = response.json()

        logger.info("Node %s pinned to group %s", certname, node_group_id)
        return result

    # -- Public API: PuppetDB Queries ---------------------------------------

    async def get_node_facts(self, certname: str) -> dict:
        """Retrieve all facts for a node from PuppetDB.

        POST /pdb/query/v4/facts
        Query: ["=", "certname", "<certname>"]

        Returns:
            A dict mapping fact names to their values.
        """
        url = self._puppetdb_url("/facts")
        query = ["=", "certname", certname]
        response = await self._post(url, json_body={"query": query})
        facts_list = response.json()

        # Transform from list of {certname, environment, name, value} dicts
        # into a flat {name: value} dict.
        facts: dict = {}
        for fact in facts_list:
            facts[fact["name"]] = fact["value"]

        logger.debug("Retrieved %d facts for node %s", len(facts), certname)
        return facts

    async def get_node_report(self, certname: str, limit: int = 1) -> list[dict]:
        """Retrieve the latest report(s) for a node from PuppetDB.

        POST /pdb/query/v4/reports
        Query: ["=", "certname", "<certname>"]

        Args:
            certname: The node's certificate name.
            limit: Maximum number of reports to return (most recent first).

        Returns:
            A list of report dicts containing status, metrics,
            configuration_version, etc.
        """
        url = self._puppetdb_url("/reports")
        query = ["=", "certname", certname]
        response = await self._post(url, json_body={"query": query})

        reports = response.json()
        # PuppetDB does not honour limit in POST body queries consistently,
        # so slice client-side as well.
        reports = reports[:limit]
        logger.debug("Retrieved %d report(s) for node %s", len(reports), certname)
        return reports

    async def get_node_status(self, certname: str) -> dict:
        """Retrieve the status of a node from PuppetDB.

        POST /pdb/query/v4/nodes
        Query: ["=", "certname", "<certname>"]

        Returns:
            Node status dict with certname, report_timestamp,
            latest_report_status, catalog_timestamp, etc.
            Returns an empty dict if the node is not yet in PuppetDB.
        """
        url = self._puppetdb_url("/nodes")
        query = ["=", "certname", certname]
        response = await self._post(url, json_body={"query": query})
        nodes = response.json()

        if not nodes:
            logger.debug("Node %s not found in PuppetDB", certname)
            return {}

        node = nodes[0]
        logger.debug(
            "Node %s status: report_status=%s, catalog_timestamp=%s",
            certname,
            node.get("latest_report_status"),
            node.get("catalog_timestamp"),
        )
        return node

    # -- Public API: Certificate Management ---------------------------------

    async def sign_certificate(self, certname: str) -> None:
        """Sign a pending Puppet agent certificate request.

        PUT /puppet-ca/v1/certificate_status/{certname}
        Body: {"desired_state": "signed"}

        If the certificate is already signed, the CA API returns a
        non-error response and this method is a no-op.
        """
        url = self._ca_url(f"/certificate_status/{certname}")
        body = {"desired_state": "signed"}
        logger.info("Signing certificate for node %s", certname)
        try:
            await self._put(url, json_body=body)
            logger.info("Certificate signed for node %s", certname)
        except PuppetError as exc:
            # If the cert is already signed, PE returns a 400/409.
            # Treat this as idempotent success.
            if exc.status_code in (400, 409):
                logger.info(
                    "Certificate for %s is already signed (status %s), continuing",
                    certname,
                    exc.status_code,
                )
            else:
                raise

    # -- Public API: Orchestrator -------------------------------------------

    async def run_puppet_on_node(self, certname: str) -> dict:
        """Trigger an on-demand Puppet agent run on a node via the Orchestrator.

        POST /orchestrator/v1/command/deploy

        The Orchestrator ``deploy`` command runs Puppet on the specified
        nodes and returns a job object with status tracking.

        Returns:
            Job details dict from the Orchestrator including job id and name.
        """
        url = self._orchestrator_url("/command/deploy")
        body = {
            "environment": self._default_environment,
            "scope": {
                "nodes": [certname],
            },
            "noop": False,
        }
        logger.info("Triggering Puppet run on node %s", certname)
        response = await self._post(url, json_body=body)
        job = response.json()
        logger.info(
            "Puppet run triggered on %s (job: %s)",
            certname,
            job.get("job", {}).get("name", "unknown"),
        )
        return job

    # -- Public API: Polling ------------------------------------------------

    async def wait_for_node_checkin(
        self,
        certname: str,
        timeout: int | None = None,
        poll_interval: int | None = None,
    ) -> dict:
        """Poll PuppetDB until the node appears with a completed Puppet run.

        This method blocks (using asyncio.sleep) until PuppetDB reports
        that the node has checked in with a catalog_timestamp, meaning
        the first Puppet agent run has completed.

        Args:
            certname: The node's certificate name.
            timeout: Maximum seconds to wait (defaults to settings).
            poll_interval: Seconds between polls (defaults to settings).

        Returns:
            The node status dict from PuppetDB.

        Raises:
            PuppetTimeoutError: If the node does not appear within the
                timeout period.
        """
        import asyncio

        timeout = timeout if timeout is not None else self._checkin_timeout
        poll_interval = poll_interval if poll_interval is not None else self._checkin_poll

        logger.info(
            "Waiting for node %s to check in (timeout=%ds, poll=%ds)",
            certname, timeout, poll_interval,
        )

        elapsed = 0
        while elapsed < timeout:
            node_status = await self.get_node_status(certname)

            # A node is considered "checked in" once it has a catalog_timestamp,
            # which means at least one successful catalog compilation + run.
            if node_status and node_status.get("catalog_timestamp"):
                logger.info(
                    "Node %s checked in after %ds (status=%s)",
                    certname,
                    elapsed,
                    node_status.get("latest_report_status"),
                )
                return node_status

            logger.debug(
                "Node %s not yet checked in (elapsed %ds/%ds)",
                certname, elapsed, timeout,
            )
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        raise PuppetTimeoutError(
            f"Node {certname} did not check in within {timeout}s"
        )

    # -- Public API: Node Purge (Decommission) ------------------------------

    async def purge_node(self, certname: str) -> None:
        """Fully purge a node from Puppet Enterprise.

        This is the reverse of enrollment and is called during server
        decommission.  Steps:

        1. Deactivate the node in PuppetDB (marks it as removed).
        2. Unpin the node from all classifier groups.
        3. Revoke the node's certificate.
        4. Delete the node's certificate from the CA.

        Each step is best-effort: failures are logged but do not prevent
        subsequent steps from executing.
        """
        logger.info("Purging node %s from Puppet Enterprise", certname)

        # 1. Deactivate node in PuppetDB
        try:
            deactivate_url = self._puppetdb_cmd_url("")
            deactivate_body = {
                "command": "deactivate node",
                "version": 3,
                "payload": {
                    "certname": certname,
                    "producer_timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
            await self._post(deactivate_url, json_body=deactivate_body)
            logger.info("Deactivated node %s in PuppetDB", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to deactivate node %s in PuppetDB: %s", certname, exc
            )

        # 2. Unpin node from all classifier groups
        try:
            groups = await self.get_node_groups()
            for group in groups:
                # Check if the node is pinned in this group by looking
                # at the rule for certname matches.
                group_id = group.get("id", "")
                try:
                    unpin_url = self._classifier_url(f"/groups/{group_id}/unpin")
                    await self._post(unpin_url, json_body={"nodes": [certname]})
                except PuppetError:
                    # Node may not be pinned to this group -- that is fine.
                    pass
            logger.info("Unpinned node %s from classifier groups", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to unpin node %s from classifier groups: %s",
                certname, exc,
            )

        # 3. Revoke the certificate
        try:
            revoke_url = self._ca_url(f"/certificate_status/{certname}")
            await self._put(revoke_url, json_body={"desired_state": "revoked"})
            logger.info("Revoked certificate for node %s", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to revoke certificate for node %s: %s", certname, exc
            )

        # 4. Delete the certificate
        try:
            delete_url = self._ca_url(f"/certificate_status/{certname}")
            await self._delete(delete_url)
            logger.info("Deleted certificate for node %s", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to delete certificate for node %s: %s", certname, exc
            )

        logger.info("Node purge complete for %s", certname)

    # -- High-level orchestration -------------------------------------------

    async def enroll_node(
        self,
        certname: str,
        puppet_role: str,
        environment: str | None = None,
    ) -> dict:
        """Enroll a newly provisioned node into Puppet Enterprise.

        This is the high-level orchestration method called by Celery tasks
        (via the sync wrapper) after AWX configuration has completed and
        the Puppet agent has been bootstrapped on the node.

        Steps:
            1. Get or create the node group for the role (e.g.
               "AnvilOps - role::web_server").
            2. Pin the node to the group.
            3. Sign the node's certificate (if pending).
            4. Wait for the first Puppet run to complete.
            5. Retrieve and verify the first report.

        Args:
            certname: The Puppet agent certificate name of the node.
            puppet_role: The Puppet role to assign (e.g. "web_server",
                         "db_server").  This maps to a Puppet class like
                         ``role::web_server``.
            environment: Puppet environment (defaults to
                         PUPPET_DEFAULT_ENVIRONMENT setting).

        Returns:
            Dict with keys: success, certname, node_group, node_group_id,
            report_status, report.
        """
        environment = environment or self._default_environment
        role_class = f"role::{puppet_role}"
        group_name = f"AnvilOps - {role_class}"

        logger.info(
            "Starting Puppet enrollment for %s (role=%s, env=%s)",
            certname, puppet_role, environment,
        )

        try:
            # 1. Get or create the node group for this role.
            #    Use "All Nodes" as the parent group.  The default "All Nodes"
            #    group in PE has a well-known UUID of "00000000-0000-4000-8000-000000000000".
            all_nodes_parent = "00000000-0000-4000-8000-000000000000"
            node_group_id = await self.get_or_create_node_group(
                name=group_name,
                parent_id=all_nodes_parent,
                environment=environment,
                classes={role_class: {}},
            )
            logger.info(
                "Node group ready: %s (id=%s)", group_name, node_group_id
            )

            # 2. Pin the node to the group.
            await self.classify_node(
                certname=certname,
                node_group_id=node_group_id,
                environment=environment,
            )

            # 3. Sign the certificate.
            #    The Puppet agent will have submitted a CSR when it first
            #    started.  If autosigning is enabled this is a no-op; if not,
            #    we sign it now so the agent can proceed.
            await self.sign_certificate(certname)

            # 4. Wait for the first Puppet run to complete.
            node_status = await self.wait_for_node_checkin(certname)
            report_status = node_status.get("latest_report_status", "unknown")

            # 5. Get the first report for verification.
            reports = await self.get_node_report(certname, limit=1)
            first_report = reports[0] if reports else {}

            success = report_status in ("changed", "unchanged")
            if not success:
                logger.warning(
                    "Puppet enrollment for %s completed but report status is '%s'",
                    certname,
                    report_status,
                )
            else:
                logger.info(
                    "Puppet enrollment succeeded for %s (report_status=%s)",
                    certname,
                    report_status,
                )

            return {
                "success": success,
                "certname": certname,
                "node_group": group_name,
                "node_group_id": node_group_id,
                "report_status": report_status,
                "report": first_report,
            }

        except PuppetTimeoutError:
            logger.error(
                "Puppet enrollment timed out waiting for node %s to check in",
                certname,
            )
            return {
                "success": False,
                "certname": certname,
                "node_group": group_name,
                "node_group_id": None,
                "report_status": "timeout",
                "report": {},
            }

        except PuppetError as exc:
            logger.exception(
                "Puppet enrollment failed for %s: %s", certname, exc
            )
            return {
                "success": False,
                "certname": certname,
                "node_group": group_name,
                "node_group_id": None,
                "report_status": "error",
                "report": {},
                "error": str(exc),
            }


# ---------------------------------------------------------------------------
# Synchronous client (for Celery tasks)
# ---------------------------------------------------------------------------


class PuppetEnterpriseServiceSync:
    """Synchronous client for the Puppet Enterprise REST APIs.

    Uses ``httpx.Client`` (blocking) so it can be called directly from Celery
    workers without an event loop.  Mirrors the async
    ``PuppetEnterpriseService`` API one-to-one.
    """

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        verify_ssl: bool | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = (base_url or settings.PUPPET_BASE_URL).rstrip("/")
        self.token = token or settings.PUPPET_API_TOKEN
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.PUPPET_VERIFY_SSL
        self._timeout = timeout
        self._headers = {
            "X-Authentication": self.token,
            "Content-Type": "application/json",
        }

        # Port configuration
        self._ca_port: int = settings.PUPPET_CA_PORT
        self._classifier_port: int = settings.PUPPET_CLASSIFIER_PORT
        self._puppetdb_port: int = settings.PUPPET_PUPPETDB_PORT
        self._orchestrator_port: int = settings.PUPPET_ORCHESTRATOR_PORT

        # Polling defaults
        self._checkin_timeout: int = settings.PUPPET_NODE_CHECKIN_TIMEOUT
        self._checkin_poll: int = settings.PUPPET_NODE_CHECKIN_POLL
        self._default_environment: str = settings.PUPPET_DEFAULT_ENVIRONMENT

        self.client = httpx.Client(
            verify=self.verify_ssl,
            timeout=self._timeout,
            headers=self._headers,
        )

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self.client.close()

    # -- URL builders -------------------------------------------------------

    def _classifier_url(self, path: str) -> str:
        """Build a full URL for the Node Classifier API."""
        return _build_url(self.base_url, self._classifier_port, f"/classifier-api/v1{path}")

    def _puppetdb_url(self, path: str) -> str:
        """Build a full URL for the PuppetDB API."""
        return _build_url(self.base_url, self._puppetdb_port, f"/pdb/query/v4{path}")

    def _puppetdb_cmd_url(self, path: str) -> str:
        """Build a full URL for the PuppetDB Command API."""
        return _build_url(self.base_url, self._puppetdb_port, f"/pdb/cmd/v1{path}")

    def _orchestrator_url(self, path: str) -> str:
        """Build a full URL for the Orchestrator API."""
        return _build_url(self.base_url, self._orchestrator_port, f"/orchestrator/v1{path}")

    def _ca_url(self, path: str) -> str:
        """Build a full URL for the Puppet CA API."""
        return _build_url(self.base_url, self._ca_port, f"/puppet-ca/v1{path}")

    # -- HTTP helpers -------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | list | None = None,
        params: dict | None = None,
    ) -> httpx.Response:
        """Execute a synchronous HTTP request against a PE API."""
        try:
            response = self.client.request(
                method,
                url,
                json=json_body,
                params=params,
            )
        except httpx.ConnectError as exc:
            raise PuppetConnectionError(
                f"Cannot connect to Puppet Enterprise at {url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise PuppetConnectionError(
                f"Request to Puppet Enterprise timed out ({url}): {exc}"
            ) from exc

        if response.status_code in (401, 403):
            raise PuppetAuthError(
                f"Puppet Enterprise authentication failed ({response.status_code}) for {url}",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        if response.status_code >= 400:
            raise PuppetError(
                f"Puppet Enterprise API error: {method} {url} returned {response.status_code}",
                status_code=response.status_code,
                response_body=response.text[:1000],
            )

        return response

    def _get(self, url: str, *, params: dict | None = None) -> httpx.Response:
        return self._request("GET", url, params=params)

    def _post(
        self, url: str, *, json_body: dict | list | None = None
    ) -> httpx.Response:
        return self._request("POST", url, json_body=json_body)

    def _put(
        self, url: str, *, json_body: dict | list | None = None
    ) -> httpx.Response:
        return self._request("PUT", url, json_body=json_body)

    def _delete(self, url: str) -> httpx.Response:
        return self._request("DELETE", url)

    # -- Public API: Health -------------------------------------------------

    def health_check(self) -> bool:
        """Return True if PuppetDB is reachable.

        GET /pdb/query/v4/version
        """
        try:
            url = self._puppetdb_url("/version")
            response = self._get(url)
            return response.status_code == 200
        except PuppetError:
            return False

    # -- Public API: Node Classifier ----------------------------------------

    def get_node_groups(self) -> list[dict]:
        """Return all node groups from the Node Classifier.

        GET /classifier-api/v1/groups
        """
        url = self._classifier_url("/groups")
        response = self._get(url)
        return response.json()

    def find_node_group_by_name(self, name: str) -> dict | None:
        """Search for a node group by exact name.

        Returns the group dict or None if not found.
        """
        groups = self.get_node_groups()
        for group in groups:
            if group.get("name") == name:
                return group
        return None

    def get_or_create_node_group(
        self,
        name: str,
        parent_id: str,
        environment: str,
        classes: dict,
        rule: list | None = None,
    ) -> str:
        """Return the ID of the named node group, creating it if necessary.

        GET  /classifier-api/v1/groups  (search by name)
        POST /classifier-api/v1/groups  (create)

        Returns:
            The UUID string of the node group.
        """
        existing = self.find_node_group_by_name(name)
        if existing:
            group_id = existing["id"]
            logger.debug("Found existing node group %s (id=%s)", name, group_id)
            return group_id

        logger.info("Creating node group: %s (parent=%s, env=%s)", name, parent_id, environment)
        body: dict = {
            "name": name,
            "parent": parent_id,
            "environment": environment,
            "classes": classes,
        }
        if rule is not None:
            body["rule"] = rule

        url = self._classifier_url("/groups")
        response = self._post(url, json_body=body)

        if response.status_code == 303:
            location = response.headers.get("location", "")
            group_id = location.rstrip("/").rsplit("/", 1)[-1]
        else:
            data = response.json()
            group_id = data.get("id", "")

        if not group_id:
            raise PuppetClassificationError(
                f"Failed to extract group ID after creating node group '{name}'",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        logger.info("Created node group %s (id=%s)", name, group_id)
        return group_id

    def classify_node(
        self,
        certname: str,
        node_group_id: str,
        environment: str = "production",
    ) -> dict:
        """Pin a node to a node group.

        POST /classifier-api/v1/groups/{node_group_id}/pin
        Body: {"nodes": [certname]}

        Returns:
            Response body from the classifier API.
        """
        url = self._classifier_url(f"/groups/{node_group_id}/pin")
        body = {"nodes": [certname]}
        logger.info(
            "Pinning node %s to group %s (env=%s)",
            certname, node_group_id, environment,
        )
        response = self._post(url, json_body=body)

        if response.status_code == 204 or not response.text.strip():
            result = {"certname": certname, "node_group_id": node_group_id, "pinned": True}
        else:
            result = response.json()

        logger.info("Node %s pinned to group %s", certname, node_group_id)
        return result

    # -- Public API: PuppetDB Queries ---------------------------------------

    def get_node_facts(self, certname: str) -> dict:
        """Retrieve all facts for a node from PuppetDB.

        POST /pdb/query/v4/facts
        Query: ["=", "certname", "<certname>"]

        Returns:
            Dict mapping fact names to their values.
        """
        url = self._puppetdb_url("/facts")
        query = ["=", "certname", certname]
        response = self._post(url, json_body={"query": query})
        facts_list = response.json()

        facts: dict = {}
        for fact in facts_list:
            facts[fact["name"]] = fact["value"]

        logger.debug("Retrieved %d facts for node %s", len(facts), certname)
        return facts

    def get_node_report(self, certname: str, limit: int = 1) -> list[dict]:
        """Retrieve the latest report(s) for a node from PuppetDB.

        POST /pdb/query/v4/reports
        Query: ["=", "certname", "<certname>"]

        Returns:
            List of report dicts (most recent first).
        """
        url = self._puppetdb_url("/reports")
        query = ["=", "certname", certname]
        response = self._post(url, json_body={"query": query})

        reports = response.json()
        reports = reports[:limit]
        logger.debug("Retrieved %d report(s) for node %s", len(reports), certname)
        return reports

    def get_node_status(self, certname: str) -> dict:
        """Retrieve the status of a node from PuppetDB.

        POST /pdb/query/v4/nodes
        Query: ["=", "certname", "<certname>"]

        Returns:
            Node status dict, or empty dict if not found.
        """
        url = self._puppetdb_url("/nodes")
        query = ["=", "certname", certname]
        response = self._post(url, json_body={"query": query})
        nodes = response.json()

        if not nodes:
            logger.debug("Node %s not found in PuppetDB", certname)
            return {}

        node = nodes[0]
        logger.debug(
            "Node %s status: report_status=%s, catalog_timestamp=%s",
            certname,
            node.get("latest_report_status"),
            node.get("catalog_timestamp"),
        )
        return node

    # -- Public API: Certificate Management ---------------------------------

    def sign_certificate(self, certname: str) -> None:
        """Sign a pending Puppet agent certificate request.

        PUT /puppet-ca/v1/certificate_status/{certname}
        Body: {"desired_state": "signed"}
        """
        url = self._ca_url(f"/certificate_status/{certname}")
        body = {"desired_state": "signed"}
        logger.info("Signing certificate for node %s", certname)
        try:
            self._put(url, json_body=body)
            logger.info("Certificate signed for node %s", certname)
        except PuppetError as exc:
            if exc.status_code in (400, 409):
                logger.info(
                    "Certificate for %s is already signed (status %s), continuing",
                    certname,
                    exc.status_code,
                )
            else:
                raise

    # -- Public API: Orchestrator -------------------------------------------

    def run_puppet_on_node(self, certname: str) -> dict:
        """Trigger an on-demand Puppet agent run on a node.

        POST /orchestrator/v1/command/deploy

        Returns:
            Job details dict from the Orchestrator.
        """
        url = self._orchestrator_url("/command/deploy")
        body = {
            "environment": self._default_environment,
            "scope": {
                "nodes": [certname],
            },
            "noop": False,
        }
        logger.info("Triggering Puppet run on node %s", certname)
        response = self._post(url, json_body=body)
        job = response.json()
        logger.info(
            "Puppet run triggered on %s (job: %s)",
            certname,
            job.get("job", {}).get("name", "unknown"),
        )
        return job

    # -- Public API: Polling ------------------------------------------------

    def wait_for_node_checkin(
        self,
        certname: str,
        timeout: int | None = None,
        poll_interval: int | None = None,
    ) -> dict:
        """Block until the node appears in PuppetDB with a completed run.

        Polls get_node_status until the node has a catalog_timestamp.

        Returns:
            The node status dict from PuppetDB.

        Raises:
            PuppetTimeoutError: If the node does not check in within the
                timeout period.
        """
        timeout = timeout if timeout is not None else self._checkin_timeout
        poll_interval = poll_interval if poll_interval is not None else self._checkin_poll

        logger.info(
            "Waiting for node %s to check in (timeout=%ds, poll=%ds)",
            certname, timeout, poll_interval,
        )

        elapsed = 0
        while elapsed < timeout:
            node_status = self.get_node_status(certname)

            if node_status and node_status.get("catalog_timestamp"):
                logger.info(
                    "Node %s checked in after %ds (status=%s)",
                    certname,
                    elapsed,
                    node_status.get("latest_report_status"),
                )
                return node_status

            logger.debug(
                "Node %s not yet checked in (elapsed %ds/%ds)",
                certname, elapsed, timeout,
            )
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise PuppetTimeoutError(
            f"Node {certname} did not check in within {timeout}s"
        )

    # -- Public API: Node Purge (Decommission) ------------------------------

    def purge_node(self, certname: str) -> None:
        """Fully purge a node from Puppet Enterprise.

        Steps:
        1. Deactivate the node in PuppetDB.
        2. Unpin the node from all classifier groups.
        3. Revoke the node's certificate.
        4. Delete the node's certificate from the CA.

        Each step is best-effort.
        """
        logger.info("Purging node %s from Puppet Enterprise", certname)

        # 1. Deactivate node in PuppetDB
        try:
            deactivate_url = self._puppetdb_cmd_url("")
            deactivate_body = {
                "command": "deactivate node",
                "version": 3,
                "payload": {
                    "certname": certname,
                    "producer_timestamp": datetime.now(timezone.utc).isoformat(),
                },
            }
            self._post(deactivate_url, json_body=deactivate_body)
            logger.info("Deactivated node %s in PuppetDB", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to deactivate node %s in PuppetDB: %s", certname, exc
            )

        # 2. Unpin node from all classifier groups
        try:
            groups = self.get_node_groups()
            for group in groups:
                group_id = group.get("id", "")
                try:
                    unpin_url = self._classifier_url(f"/groups/{group_id}/unpin")
                    self._post(unpin_url, json_body={"nodes": [certname]})
                except PuppetError:
                    pass
            logger.info("Unpinned node %s from classifier groups", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to unpin node %s from classifier groups: %s",
                certname, exc,
            )

        # 3. Revoke the certificate
        try:
            revoke_url = self._ca_url(f"/certificate_status/{certname}")
            self._put(revoke_url, json_body={"desired_state": "revoked"})
            logger.info("Revoked certificate for node %s", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to revoke certificate for node %s: %s", certname, exc
            )

        # 4. Delete the certificate
        try:
            delete_url = self._ca_url(f"/certificate_status/{certname}")
            self._delete(delete_url)
            logger.info("Deleted certificate for node %s", certname)
        except PuppetError as exc:
            logger.warning(
                "Failed to delete certificate for node %s: %s", certname, exc
            )

        logger.info("Node purge complete for %s", certname)

    # -- High-level orchestration -------------------------------------------

    def enroll_node(
        self,
        certname: str,
        puppet_role: str,
        environment: str | None = None,
    ) -> dict:
        """Enroll a newly provisioned node into Puppet Enterprise.

        This is the main entry point called from Celery tasks after AWX
        configuration has completed.

        Steps:
            1. Get or create the node group for the role.
            2. Pin the node to the group.
            3. Sign the certificate (if pending).
            4. Wait for the first Puppet run to complete.
            5. Get the first report and verify status.

        Args:
            certname: The Puppet agent certificate name.
            puppet_role: The Puppet role (e.g. "web_server").
            environment: Puppet environment (defaults to setting).

        Returns:
            Dict with: success, certname, node_group, node_group_id,
            report_status, report.
        """
        environment = environment or self._default_environment
        role_class = f"role::{puppet_role}"
        group_name = f"AnvilOps - {role_class}"

        logger.info(
            "Starting Puppet enrollment for %s (role=%s, env=%s)",
            certname, puppet_role, environment,
        )

        try:
            # 1. Get or create the node group for this role.
            all_nodes_parent = "00000000-0000-4000-8000-000000000000"
            node_group_id = self.get_or_create_node_group(
                name=group_name,
                parent_id=all_nodes_parent,
                environment=environment,
                classes={role_class: {}},
            )
            logger.info(
                "Node group ready: %s (id=%s)", group_name, node_group_id
            )

            # 2. Pin the node to the group.
            self.classify_node(
                certname=certname,
                node_group_id=node_group_id,
                environment=environment,
            )

            # 3. Sign the certificate.
            self.sign_certificate(certname)

            # 4. Wait for the first Puppet run to complete.
            node_status = self.wait_for_node_checkin(certname)
            report_status = node_status.get("latest_report_status", "unknown")

            # 5. Get the first report for verification.
            reports = self.get_node_report(certname, limit=1)
            first_report = reports[0] if reports else {}

            success = report_status in ("changed", "unchanged")
            if not success:
                logger.warning(
                    "Puppet enrollment for %s completed but report status is '%s'",
                    certname,
                    report_status,
                )
            else:
                logger.info(
                    "Puppet enrollment succeeded for %s (report_status=%s)",
                    certname,
                    report_status,
                )

            return {
                "success": success,
                "certname": certname,
                "node_group": group_name,
                "node_group_id": node_group_id,
                "report_status": report_status,
                "report": first_report,
            }

        except PuppetTimeoutError:
            logger.error(
                "Puppet enrollment timed out waiting for node %s to check in",
                certname,
            )
            return {
                "success": False,
                "certname": certname,
                "node_group": group_name,
                "node_group_id": None,
                "report_status": "timeout",
                "report": {},
            }

        except PuppetError as exc:
            logger.exception(
                "Puppet enrollment failed for %s: %s", certname, exc
            )
            return {
                "success": False,
                "certname": certname,
                "node_group": group_name,
                "node_group_id": None,
                "report_status": "error",
                "report": {},
                "error": str(exc),
            }
