"""CMDB synchronization service.

Coordinates CI lifecycle in ServiceNow based on AnvilOps server events.
Called from Celery tasks after key pipeline milestones.

All operations are best-effort: errors are logged but never raised so
that CMDB sync failures cannot block or slow the build pipeline.
"""

import logging
from datetime import datetime, timezone

from app.services.servicenow import ServiceNowClient, get_servicenow_client

logger = logging.getLogger(__name__)


class CMDBSyncService:
    """Orchestrate CMDB sync operations for AnvilOps server lifecycle.

    Wraps :class:`~app.services.servicenow.ServiceNowClient` with
    higher-level methods that handle the mapping between AnvilOps
    server events and CMDB CI operations.

    Parameters
    ----------
    client:
        An optional ``ServiceNowClient`` instance.  When ``None`` (the
        default), one is created from application settings via
        :func:`~app.services.servicenow.get_servicenow_client`.
    """

    def __init__(self, client: ServiceNowClient | None = None):
        self.client = client or get_servicenow_client()

    def sync_server_created(self, server_data: dict) -> dict | None:
        """Create CI when a server build completes successfully.

        If a CI with the same server name already exists in CMDB (e.g.
        from a previous build that was not cleaned up), it is updated
        instead of creating a duplicate.

        Parameters
        ----------
        server_data:
            Dict with AnvilOps server fields (as returned by
            ``app.services.db.get_server_request``).

        Returns
        -------
        dict or None
            ``{"sys_id": ..., "action": "created"|"updated", ...}`` on
            success, ``None`` on failure.
        """
        server_name = server_data.get("server_name", "unknown")
        logger.info("CMDB sync: server_created for %s", server_name)

        try:
            # Check if a CI already exists for this server name
            existing = self.client.find_ci_by_name(server_name)

            if existing:
                sys_id = existing.get("sys_id", "")
                logger.info(
                    "CMDB CI already exists for %s (sys_id=%s), updating",
                    server_name,
                    sys_id,
                )
                updates = self._build_ci_updates(server_data)
                result = self.client.update_ci(sys_id, updates)
                if result:
                    return {
                        "sys_id": sys_id,
                        "action": "updated",
                        "server_name": server_name,
                    }
                return None

            # Create a new CI
            result = self.client.create_ci(server_data)
            if result:
                return {
                    "sys_id": result["sys_id"],
                    "action": "created",
                    "server_name": server_name,
                    "ci_number": result.get("ci_number", ""),
                }

            return None

        except Exception as exc:
            logger.exception(
                "CMDB sync_server_created failed for %s: %s",
                server_name,
                exc,
            )
            return None

    def sync_server_updated(
        self, server_data: dict, cmdb_sys_id: str
    ) -> dict | None:
        """Update CI when server metadata changes.

        Called when server status changes, IP addresses are assigned,
        Puppet enrollment completes, etc.

        Parameters
        ----------
        server_data:
            Dict with current AnvilOps server fields.
        cmdb_sys_id:
            The ServiceNow ``sys_id`` of the existing CI.

        Returns
        -------
        dict or None
            ``{"sys_id": ..., "action": "updated", ...}`` on success,
            ``None`` on failure.
        """
        server_name = server_data.get("server_name", "unknown")
        logger.info(
            "CMDB sync: server_updated for %s (sys_id=%s)",
            server_name,
            cmdb_sys_id,
        )

        if not cmdb_sys_id:
            logger.warning(
                "No cmdb_sys_id for %s, attempting lookup by name",
                server_name,
            )
            existing = self.client.find_ci_by_name(server_name)
            if existing:
                cmdb_sys_id = existing.get("sys_id", "")
            else:
                logger.warning(
                    "No CMDB CI found for %s, creating new CI", server_name
                )
                return self.sync_server_created(server_data)

        try:
            updates = self._build_ci_updates(server_data)
            result = self.client.update_ci(cmdb_sys_id, updates)
            if result:
                return {
                    "sys_id": cmdb_sys_id,
                    "action": "updated",
                    "server_name": server_name,
                }
            return None

        except Exception as exc:
            logger.exception(
                "CMDB sync_server_updated failed for %s: %s",
                server_name,
                exc,
            )
            return None

    def sync_server_decommissioned(
        self, server_data: dict, cmdb_sys_id: str
    ) -> dict | None:
        """Retire CI when server is decommissioned.

        Sets the CI status to Retired in ServiceNow.  If no
        ``cmdb_sys_id`` is provided, attempts to find the CI by server
        name.

        Parameters
        ----------
        server_data:
            Dict with AnvilOps server fields.
        cmdb_sys_id:
            The ServiceNow ``sys_id`` of the CI to retire.

        Returns
        -------
        dict or None
            ``{"sys_id": ..., "action": "retired", ...}`` on success,
            ``None`` on failure.
        """
        server_name = server_data.get("server_name", "unknown")
        logger.info(
            "CMDB sync: server_decommissioned for %s (sys_id=%s)",
            server_name,
            cmdb_sys_id,
        )

        if not cmdb_sys_id:
            logger.warning(
                "No cmdb_sys_id for %s, attempting lookup by name",
                server_name,
            )
            existing = self.client.find_ci_by_name(server_name)
            if existing:
                cmdb_sys_id = existing.get("sys_id", "")
            else:
                logger.warning(
                    "No CMDB CI found for %s, nothing to retire",
                    server_name,
                )
                return None

        try:
            result = self.client.retire_ci(cmdb_sys_id)
            if result:
                return {
                    "sys_id": cmdb_sys_id,
                    "action": "retired",
                    "server_name": server_name,
                }
            return None

        except Exception as exc:
            logger.exception(
                "CMDB sync_server_decommissioned failed for %s: %s",
                server_name,
                exc,
            )
            return None

    def full_sync(self, servers: list[dict]) -> dict:
        """Reconcile all servers against CMDB.

        Iterates through every server and ensures the corresponding
        CMDB CI exists and is up to date.  Servers without a
        ``cmdb_sys_id`` get one created; servers with one get updated.
        Decommissioned servers have their CIs retired.

        Parameters
        ----------
        servers:
            List of server data dicts (each as returned by
            ``app.services.db.get_server_request``).

        Returns
        -------
        dict
            Sync statistics: ``{"total", "created", "updated",
            "retired", "failed", "skipped", "errors"}``.
        """
        logger.info("CMDB full sync: processing %d servers", len(servers))

        stats = {
            "total": len(servers),
            "created": 0,
            "updated": 0,
            "retired": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

        for server_data in servers:
            server_name = server_data.get("server_name", "unknown")
            server_status = server_data.get("status", "")
            cmdb_sys_id = server_data.get("cmdb_sys_id", "")

            try:
                if server_status == "decommissioned":
                    if cmdb_sys_id:
                        result = self.sync_server_decommissioned(
                            server_data, cmdb_sys_id
                        )
                        if result:
                            stats["retired"] += 1
                        else:
                            stats["failed"] += 1
                    else:
                        # No CMDB record to retire
                        stats["skipped"] += 1
                    continue

                if server_status == "pending":
                    # Server hasn't been provisioned yet, skip
                    stats["skipped"] += 1
                    continue

                if cmdb_sys_id:
                    result = self.sync_server_updated(
                        server_data, cmdb_sys_id
                    )
                    if result:
                        action = result.get("action", "updated")
                        stats[action] = stats.get(action, 0) + 1
                    else:
                        stats["failed"] += 1
                else:
                    result = self.sync_server_created(server_data)
                    if result:
                        action = result.get("action", "created")
                        stats[action] = stats.get(action, 0) + 1
                    else:
                        stats["failed"] += 1

            except Exception as exc:
                logger.exception(
                    "CMDB full_sync error for %s: %s", server_name, exc
                )
                stats["failed"] += 1
                stats["errors"].append(
                    {
                        "server_name": server_name,
                        "error": str(exc)[:500],
                    }
                )

        logger.info(
            "CMDB full sync complete: %d created, %d updated, "
            "%d retired, %d failed, %d skipped",
            stats["created"],
            stats["updated"],
            stats["retired"],
            stats["failed"],
            stats["skipped"],
        )

        return stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_ci_updates(self, server_data: dict) -> dict:
        """Build a dict of CMDB field updates from server data.

        Only includes fields that have non-empty values to avoid
        overwriting existing CMDB data with blanks.
        """
        operational_status, install_status = self.client._map_status(
            server_data.get("status", "pending")
        )

        updates: dict[str, str] = {
            "operational_status": str(operational_status),
            "install_status": str(install_status),
        }

        # Map optional fields -- only include non-empty values
        field_map = {
            "ip_address": "private_ip",
            "dns_domain": "dns_name",
            "os": None,  # handled separately
            "u_puppet_certname": "puppet_certname",
            "u_aws_instance_id": "aws_instance_id",
            "u_aws_region": "region",
        }

        for cmdb_field, server_field in field_map.items():
            if server_field is None:
                continue
            value = server_data.get(server_field, "")
            if value:
                updates[cmdb_field] = str(value)

        # OS type requires mapping
        os_type = server_data.get("os_type", "")
        if os_type:
            updates["os"] = self.client._map_os_type(os_type)

        # Environment requires mapping
        environment = server_data.get("environment", "")
        if environment:
            updates["environment"] = self.client._map_environment(environment)

        return updates
