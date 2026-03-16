"""
Puppet status and compliance API endpoints.

Provides read-only access to Puppet Enterprise data for servers managed
by AnvilOps.  All enrollment and classification mutations happen via
Celery tasks — these endpoints only query PuppetDB for node status,
reports, facts, and aggregate compliance metrics.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.db.session import get_db
from app.models.server import ServerRequest
from app.services.puppet_classifier import get_certname

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Import PuppetEnterpriseService with graceful fallback.
# The service module is being built by another agent and may not be
# available yet.  Endpoints that need it check _puppet_available at
# runtime and return 503 if the service cannot be loaded.
# ---------------------------------------------------------------------------

_puppet_available = False

try:
    from app.services.puppet import PuppetEnterpriseService  # type: ignore[import-untyped]

    _puppet_available = True
except ImportError:
    logger.warning(
        "PuppetEnterpriseService not available; Puppet endpoints will return 503"
    )
    PuppetEnterpriseService = None  # type: ignore[assignment,misc]

try:
    from app.services.puppet import PuppetError  # type: ignore[import-untyped]
except ImportError:
    # Define a local stand-in so except clauses don't break at parse time.
    class PuppetError(Exception):  # type: ignore[no-redef]
        """Stand-in when the real PuppetError is not importable."""


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PuppetNodeStatus(BaseModel):
    """Status of a single node as reported by PuppetDB."""

    certname: str
    server_id: uuid.UUID
    server_name: str
    deactivated: bool = False
    latest_report_status: str | None = Field(
        None, description="unchanged, changed, or failed"
    )
    latest_report_hash: str | None = None
    report_timestamp: str | None = Field(
        None, description="ISO-8601 timestamp of the most recent report"
    )
    catalog_timestamp: str | None = Field(
        None, description="ISO-8601 timestamp of the last compiled catalog"
    )
    facts_timestamp: str | None = Field(
        None, description="ISO-8601 timestamp of the last facts submission"
    )
    report_environment: str | None = None


class PuppetReport(BaseModel):
    """Most recent Puppet report for a node."""

    certname: str
    server_id: uuid.UUID
    hash: str | None = None
    status: str | None = Field(
        None, description="unchanged, changed, or failed"
    )
    environment: str | None = None
    configuration_version: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    report_format: int | None = None
    resource_events: dict = Field(
        default_factory=dict,
        description="Counts of resource events by status",
    )
    metrics: dict = Field(
        default_factory=dict,
        description="Report metrics (resources, time, events, changes)",
    )


class PuppetFacts(BaseModel):
    """Key Puppet facts for a node."""

    certname: str
    server_id: uuid.UUID
    facts: dict = Field(
        default_factory=dict,
        description="Selected Puppet facts (os, networking, memory, processors, etc.)",
    )


class PuppetComplianceSummary(BaseModel):
    """Aggregate compliance summary across all AnvilOps-managed nodes."""

    total_nodes: int = 0
    compliant: int = Field(0, description="Nodes with 'unchanged' status")
    changed: int = Field(0, description="Nodes with 'changed' status")
    failed: int = Field(0, description="Nodes with 'failed' status")
    unresponsive: int = Field(
        0, description="Nodes with no recent report"
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_puppet_service() -> "PuppetEnterpriseService":
    """Instantiate and return the Puppet service, or raise 503."""
    if not _puppet_available or PuppetEnterpriseService is None:
        raise HTTPException(
            status_code=503,
            detail="Puppet Enterprise service is not available",
        )
    return PuppetEnterpriseService()


async def _resolve_certname(
    server_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[ServerRequest, str]:
    """Look up the ServerRequest and derive its Puppet certname.

    Returns a (server_request, certname) tuple.
    Raises 404 if the server request does not exist.
    """
    result = await db.execute(
        select(ServerRequest).where(ServerRequest.id == server_id)
    )
    server = result.scalar_one_or_none()

    if server is None:
        raise HTTPException(status_code=404, detail="Server request not found")

    certname = get_certname(server.server_name)
    return server, certname


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/nodes/{server_id}/status",
    response_model=PuppetNodeStatus,
    summary="Get Puppet node status",
    description="Return the current Puppet status for a managed server.",
)
async def get_node_status(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PuppetNodeStatus:
    """Fetch the PuppetDB node record for the given AnvilOps server."""
    server, certname = await _resolve_certname(server_id, db)
    puppet = _get_puppet_service()

    try:
        node_data = puppet.get_node_status(certname)
    except PuppetError as exc:
        logger.error("Puppet API error fetching status for %s: %s", certname, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to reach Puppet Enterprise: {exc}",
        ) from exc

    if node_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Node '{certname}' not found in PuppetDB",
        )

    return PuppetNodeStatus(
        certname=certname,
        server_id=server.id,
        server_name=server.server_name,
        deactivated=node_data.get("deactivated") is not None,
        latest_report_status=node_data.get("latest_report_status"),
        latest_report_hash=node_data.get("latest_report_hash"),
        report_timestamp=node_data.get("report_timestamp"),
        catalog_timestamp=node_data.get("catalog_timestamp"),
        facts_timestamp=node_data.get("facts_timestamp"),
        report_environment=node_data.get("report_environment"),
    )


@router.get(
    "/nodes/{server_id}/report",
    response_model=PuppetReport,
    summary="Get latest Puppet report",
    description="Return the most recent Puppet run report for a managed server.",
)
async def get_latest_report(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PuppetReport:
    """Fetch the latest Puppet report from PuppetDB for a server."""
    server, certname = await _resolve_certname(server_id, db)
    puppet = _get_puppet_service()

    try:
        report_data = puppet.get_latest_report(certname)
    except PuppetError as exc:
        logger.error("Puppet API error fetching report for %s: %s", certname, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to reach Puppet Enterprise: {exc}",
        ) from exc

    if report_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Puppet reports found for node '{certname}'",
        )

    # Extract resource event counts and metrics from the report if present.
    resource_events: dict = {}
    metrics: dict = {}

    if "resource_events" in report_data:
        events = report_data["resource_events"]
        if isinstance(events, dict) and "data" in events:
            # PuppetDB returns events under a "data" key
            for event in events["data"]:
                status = event.get("status", "unknown")
                resource_events[status] = resource_events.get(status, 0) + 1
        elif isinstance(events, list):
            for event in events:
                status = event.get("status", "unknown")
                resource_events[status] = resource_events.get(status, 0) + 1

    if "metrics" in report_data:
        raw_metrics = report_data["metrics"]
        if isinstance(raw_metrics, dict) and "data" in raw_metrics:
            for metric in raw_metrics["data"]:
                category = metric.get("category", "unknown")
                name = metric.get("name", "unknown")
                value = metric.get("value", 0)
                metrics.setdefault(category, {})[name] = value
        elif isinstance(raw_metrics, list):
            for metric in raw_metrics:
                category = metric.get("category", "unknown")
                name = metric.get("name", "unknown")
                value = metric.get("value", 0)
                metrics.setdefault(category, {})[name] = value
        elif isinstance(raw_metrics, dict):
            metrics = raw_metrics

    return PuppetReport(
        certname=certname,
        server_id=server.id,
        hash=report_data.get("hash"),
        status=report_data.get("status"),
        environment=report_data.get("environment"),
        configuration_version=report_data.get("configuration_version"),
        start_time=report_data.get("start_time"),
        end_time=report_data.get("end_time"),
        report_format=report_data.get("report_format"),
        resource_events=resource_events,
        metrics=metrics,
    )


@router.get(
    "/nodes/{server_id}/facts",
    response_model=PuppetFacts,
    summary="Get Puppet facts",
    description="Return key Puppet facts for a managed server (OS, networking, memory, etc.).",
)
async def get_node_facts(
    user: CurrentUser,
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PuppetFacts:
    """Fetch selected Puppet facts from PuppetDB for a server."""
    server, certname = await _resolve_certname(server_id, db)
    puppet = _get_puppet_service()

    # Facts we want to expose through the API.
    interesting_facts = [
        "os",
        "networking",
        "memory",
        "processors",
        "disks",
        "mountpoints",
        "kernel",
        "kernelversion",
        "fqdn",
        "ipaddress",
        "uptime",
        "uptime_seconds",
        "virtual",
        "is_virtual",
        "timezone",
        "domain",
    ]

    try:
        facts_data = puppet.get_node_facts(certname)
    except PuppetError as exc:
        logger.error("Puppet API error fetching facts for %s: %s", certname, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to reach Puppet Enterprise: {exc}",
        ) from exc

    if facts_data is None:
        raise HTTPException(
            status_code=404,
            detail=f"No Puppet facts found for node '{certname}'",
        )

    # Filter to only the interesting subset.  The raw PuppetDB response
    # may return facts as a list of {name, value} dicts or as a flat dict
    # depending on the query style used by PuppetEnterpriseService.
    filtered_facts: dict = {}
    if isinstance(facts_data, dict):
        for fact_name in interesting_facts:
            if fact_name in facts_data:
                filtered_facts[fact_name] = facts_data[fact_name]
    elif isinstance(facts_data, list):
        for entry in facts_data:
            name = entry.get("name", "")
            if name in interesting_facts:
                filtered_facts[name] = entry.get("value")

    return PuppetFacts(
        certname=certname,
        server_id=server.id,
        facts=filtered_facts,
    )


@router.get(
    "/compliance",
    response_model=PuppetComplianceSummary,
    summary="Get compliance summary",
    description="Return aggregate Puppet compliance across all AnvilOps-managed servers.",
)
async def get_compliance_summary(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> PuppetComplianceSummary:
    """Query PuppetDB for all AnvilOps-managed nodes and aggregate compliance."""
    puppet = _get_puppet_service()

    # Load all active server requests to know which certnames are ours.
    result = await db.execute(
        select(ServerRequest).where(
            ServerRequest.status.notin_(["decommissioned", "failed", "pending"])
        )
    )
    servers = result.scalars().all()

    if not servers:
        return PuppetComplianceSummary()

    certname_map: dict[str, ServerRequest] = {
        get_certname(s.server_name): s for s in servers
    }

    total = 0
    compliant = 0
    changed = 0
    failed = 0
    unresponsive = 0

    try:
        all_nodes = puppet.get_all_nodes()
    except PuppetError as exc:
        logger.error("Puppet API error fetching all nodes: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Failed to reach Puppet Enterprise: {exc}",
        ) from exc

    if all_nodes is None:
        all_nodes = []

    # Build a lookup of PuppetDB nodes by certname.
    puppet_node_map: dict[str, dict] = {}
    for node in all_nodes:
        cn = node.get("certname", "")
        if cn:
            puppet_node_map[cn] = node

    for certname in certname_map:
        node = puppet_node_map.get(certname)
        if node is None:
            # Server exists in AnvilOps but not yet in PuppetDB —
            # treat as unresponsive (enrollment may still be pending).
            unresponsive += 1
            total += 1
            continue

        total += 1
        status = node.get("latest_report_status")
        if status == "unchanged":
            compliant += 1
        elif status == "changed":
            changed += 1
        elif status == "failed":
            failed += 1
        else:
            # No report or unrecognised status.
            unresponsive += 1

    return PuppetComplianceSummary(
        total_nodes=total,
        compliant=compliant,
        changed=changed,
        failed=failed,
        unresponsive=unresponsive,
    )
