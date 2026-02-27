"""Compliance and reporting API endpoints.

Exposes Puppet Enterprise compliance data through REST endpoints for
dashboards, per-node detail views, drift analysis, and audit exports.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.server import ServerRequest

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Puppet service factory (resilient import)
# ---------------------------------------------------------------------------


def _get_puppet_service() -> Any:
    """Instantiate PuppetEnterpriseServiceSync for compliance queries.

    Uses try/except so the compliance module loads even if the puppet
    service package is not yet installed or configured.

    Returns:
        A PuppetEnterpriseServiceSync instance.

    Raises:
        HTTPException(503): If the Puppet service cannot be imported or
            instantiated.
    """
    try:
        from app.services.puppet import PuppetEnterpriseServiceSync
    except ImportError:
        logger.error("Puppet service module not available")
        raise HTTPException(
            status_code=503,
            detail="Puppet Enterprise service is not available",
        )

    try:
        return PuppetEnterpriseServiceSync()
    except Exception as exc:
        logger.error("Failed to instantiate Puppet service: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Puppet Enterprise service could not be initialised",
        )


def _get_compliance_service() -> Any:
    """Instantiate PuppetComplianceService with a live Puppet client.

    Returns:
        A PuppetComplianceService instance.

    Raises:
        HTTPException(503): If underlying Puppet service is unavailable.
    """
    try:
        from app.services.puppet_reports import PuppetComplianceService
    except ImportError:
        logger.error("Puppet compliance reports module not available")
        raise HTTPException(
            status_code=503,
            detail="Compliance reporting service is not available",
        )

    puppet_service = _get_puppet_service()
    return PuppetComplianceService(puppet_service)


# ---------------------------------------------------------------------------
# Helper: look up a server and its certname
# ---------------------------------------------------------------------------


async def _get_server_with_certname(
    server_id: uuid.UUID, db: AsyncSession
) -> ServerRequest:
    """Load a ServerRequest by ID and verify it has a puppet_certname.

    Raises:
        HTTPException(404): Server not found.
        HTTPException(400): Server has no Puppet certname (not enrolled).
    """
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    if not server.puppet_certname:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Server {server.server_name} is not enrolled in "
                f"Puppet Enterprise (no certname)"
            ),
        )

    return server


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/summary")
async def get_compliance_summary(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fleet-wide compliance summary.

    Queries all server requests with status ``ready`` and a non-null
    ``puppet_certname``, then aggregates their Puppet compliance data.
    """
    result = await db.execute(
        select(ServerRequest).where(
            ServerRequest.status == "ready",
            ServerRequest.puppet_certname.isnot(None),
        )
    )
    servers = result.scalars().all()

    if not servers:
        return {
            "total": 0,
            "compliant": 0,
            "changed": 0,
            "failed": 0,
            "unresponsive": 0,
            "compliance_rate": 0.0,
            "nodes": [],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    certnames = [s.puppet_certname for s in servers]

    compliance_svc = _get_compliance_service()

    try:
        summary = compliance_svc.get_fleet_compliance(certnames)
    except Exception as exc:
        logger.error("PuppetDB query failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to reach Puppet Enterprise. Please try again later.",
        )

    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    return summary


@router.get("/nodes/{server_id}")
async def get_node_compliance(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Single node compliance detail.

    Returns detailed compliance information for the given server,
    including resource counts, corrective changes, and uptime.
    """
    server = await _get_server_with_certname(server_id, db)

    compliance_svc = _get_compliance_service()

    try:
        node_data = compliance_svc.get_node_compliance(server.puppet_certname)
    except Exception as exc:
        logger.error(
            "PuppetDB query failed for %s: %s",
            server.puppet_certname,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to reach Puppet Enterprise. Please try again later.",
        )

    node_data["server_id"] = str(server.id)
    node_data["server_name"] = server.server_name
    return node_data


@router.get("/nodes/{server_id}/drift")
async def get_node_drift(
    server_id: uuid.UUID,
    hours: int = Query(24, ge=1, le=720, description="Lookback period in hours"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Drift report for a single node.

    Returns drift events detected over the specified lookback window.
    The ``resources_corrected`` list shows which Puppet resources had
    to be remediated during the period.
    """
    server = await _get_server_with_certname(server_id, db)

    compliance_svc = _get_compliance_service()

    try:
        drift_data = compliance_svc.get_node_drift_report(
            server.puppet_certname, hours=hours
        )
    except Exception as exc:
        logger.error(
            "PuppetDB drift query failed for %s: %s",
            server.puppet_certname,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to reach Puppet Enterprise. Please try again later.",
        )

    drift_data["server_id"] = str(server.id)
    drift_data["server_name"] = server.server_name
    return drift_data


@router.get("/report")
async def get_compliance_report(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Downloadable compliance report for all managed nodes.

    Returns a JSON document suitable for audit purposes containing
    full compliance details for every Puppet-enrolled server.
    """
    result = await db.execute(
        select(ServerRequest).where(
            ServerRequest.status == "ready",
            ServerRequest.puppet_certname.isnot(None),
        )
    )
    servers = result.scalars().all()

    if not servers:
        return {
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "total_nodes": 0,
            "nodes": [],
            "summary": {
                "compliant": 0,
                "changed": 0,
                "failed": 0,
                "unresponsive": 0,
                "compliance_rate": 0.0,
            },
        }

    certnames = [s.puppet_certname for s in servers]

    # Build a certname -> server mapping for enrichment
    certname_to_server: dict[str, ServerRequest] = {
        s.puppet_certname: s for s in servers
    }

    compliance_svc = _get_compliance_service()

    try:
        fleet_data = compliance_svc.get_fleet_compliance(certnames)
    except Exception as exc:
        logger.error("PuppetDB query failed for report: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to reach Puppet Enterprise. Please try again later.",
        )

    # Enrich each node entry with server metadata
    enriched_nodes = []
    for node in fleet_data.get("nodes", []):
        certname = node.get("certname", "")
        server = certname_to_server.get(certname)
        if server:
            node["server_id"] = str(server.id)
            node["server_name"] = server.server_name
            node["os_type"] = server.os_type
            node["instance_size"] = server.instance_size
            node["region"] = server.region
            node["puppet_role"] = server.puppet_role
            node["puppet_enrolled_at"] = (
                server.puppet_enrolled_at.isoformat()
                if server.puppet_enrolled_at
                else None
            )
        enriched_nodes.append(node)

    return {
        "report_generated_at": datetime.now(timezone.utc).isoformat(),
        "total_nodes": fleet_data["total"],
        "summary": {
            "compliant": fleet_data["compliant"],
            "changed": fleet_data["changed"],
            "failed": fleet_data["failed"],
            "unresponsive": fleet_data["unresponsive"],
            "compliance_rate": fleet_data["compliance_rate"],
        },
        "nodes": enriched_nodes,
    }
