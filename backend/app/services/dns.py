"""
DNS record cleanup service for AnvilOps decommission workflow.

Removes DNS records associated with decommissioned servers.  Currently a
stub -- will integrate with Amazon Route 53 in Phase 4.

When fully implemented this service will:
  1. Look up A/CNAME records for the server's DNS name in Route 53.
  2. Delete the matching record sets from the appropriate hosted zone.
  3. Optionally remove PTR records for reverse DNS.

The stub always returns success so the decommission pipeline can
proceed without a real DNS provider.
"""

import logging

logger = logging.getLogger(__name__)


class DNSCleanupService:
    """Stub service for cleaning up DNS records during server decommission.

    In Phase 4 this will use boto3 to interact with Route 53 hosted zones.
    For now it logs what *would* be cleaned up and returns success.
    """

    def cleanup_records(
        self,
        server_name: str,
        dns_name: str | None = None,
        private_ip: str | None = None,
        public_ip: str | None = None,
    ) -> dict:
        """Remove DNS records for a decommissioned server.

        Args:
            server_name: The AnvilOps server name (e.g. ``PROD-WEB-a3f8``).
            dns_name: The FQDN assigned to the server (if any).
            private_ip: The private IP address whose A record should be
                removed (if any).
            public_ip: The public/elastic IP address whose A record should
                be removed (if any).

        Returns:
            Dict with ``exit_code`` (0 = success, 1 = failure) and
            ``output`` (human-readable log of actions taken).
        """
        actions: list[str] = []

        if dns_name:
            actions.append(f"Would delete DNS record for {dns_name}")
            logger.info(
                "DNS cleanup stub: would delete record for %s (server %s)",
                dns_name,
                server_name,
            )

        if private_ip:
            actions.append(
                f"Would delete A record for private IP {private_ip}"
            )
            logger.info(
                "DNS cleanup stub: would delete A record for private IP %s (server %s)",
                private_ip,
                server_name,
            )

        if public_ip:
            actions.append(
                f"Would delete A record for public IP {public_ip}"
            )
            logger.info(
                "DNS cleanup stub: would delete A record for public IP %s (server %s)",
                public_ip,
                server_name,
            )

        if not actions:
            actions.append("No DNS records to clean up")
            logger.info(
                "DNS cleanup stub: no records to clean up for server %s",
                server_name,
            )

        output = (
            f"DNS cleanup stub for {server_name}:\n"
            + "\n".join(f"  - {a}" for a in actions)
        )

        return {"exit_code": 0, "output": output}
