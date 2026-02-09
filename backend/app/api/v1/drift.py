"""Drift detection API endpoints.

Exposes drift events, alerts, summaries, timelines, and trending data
for the AnvilOps frontend dashboard.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.drift import (
    AcknowledgeAlertRequest,
    AcknowledgeAlertResponse,
    DriftAlertListResponse,
    DriftAlertResponse,
    DriftCategoryCount,
    DriftEventListResponse,
    DriftEventResponse,
    DriftSeverityCount,
    DriftSummaryResponse,
    DriftTimelineEntry,
    DriftTimelineResponse,
    DriftTrendDay,
    DriftTrendsResponse,
)
from app.services.drift_monitor import AsyncDriftMonitor

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helper: instantiate the async drift monitor
# ---------------------------------------------------------------------------


def _get_monitor(db: AsyncSession) -> AsyncDriftMonitor:
    """Create an AsyncDriftMonitor bound to the current DB session."""
    return AsyncDriftMonitor(db)


# ---------------------------------------------------------------------------
# GET /drift/summary
# ---------------------------------------------------------------------------


@router.get("/summary", response_model=DriftSummaryResponse)
async def get_drift_summary(
    db: AsyncSession = Depends(get_db),
):
    """Fleet-wide drift summary.

    Returns total drift events, counts by severity and category,
    number of active alerts, and affected servers.
    """
    monitor = _get_monitor(db)

    try:
        data = await monitor.get_drift_summary()
    except Exception as exc:
        logger.error("Failed to generate drift summary: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to generate drift summary. Please try again later.",
        )

    return DriftSummaryResponse(
        total_events=data["total_events"],
        unresolved_events=data["unresolved_events"],
        resolved_events=data["resolved_events"],
        auto_corrected=data["auto_corrected"],
        active_alerts=data["active_alerts"],
        affected_servers=data["affected_servers"],
        by_severity=DriftSeverityCount(**data["by_severity"]),
        by_category=DriftCategoryCount(**data["by_category"]),
        generated_at=data["generated_at"],
    )


# ---------------------------------------------------------------------------
# GET /drift/events
# ---------------------------------------------------------------------------


@router.get("/events", response_model=DriftEventListResponse)
async def list_drift_events(
    server_id: uuid.UUID | None = Query(None, description="Filter by server request ID"),
    severity: str | None = Query(None, description="Filter by severity: critical, high, medium, low"),
    category: str | None = Query(None, description="Filter by category: security, configuration, package, service, file"),
    is_resolved: bool | None = Query(None, description="Filter by resolution status"),
    date_from: datetime | None = Query(None, description="Start of date range (ISO 8601)"),
    date_to: datetime | None = Query(None, description="End of date range (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """List drift events with filtering and pagination.

    Supports filtering by server, severity, category, resolution status,
    and date range.
    """
    monitor = _get_monitor(db)

    try:
        data = await monitor.get_drift_events(
            server_id=str(server_id) if server_id else None,
            severity=severity,
            category=category,
            is_resolved=is_resolved,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.error("Failed to list drift events: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve drift events. Please try again later.",
        )

    return DriftEventListResponse(
        events=[DriftEventResponse.model_validate(e) for e in data["events"]],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
    )


# ---------------------------------------------------------------------------
# GET /drift/events/{event_id}
# ---------------------------------------------------------------------------


@router.get("/events/{event_id}", response_model=DriftEventResponse)
async def get_drift_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single drift event by ID."""
    monitor = _get_monitor(db)

    try:
        event = await monitor.get_drift_event_by_id(str(event_id))
    except Exception as exc:
        logger.error("Failed to fetch drift event %s: %s", event_id, exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve drift event. Please try again later.",
        )

    if event is None:
        raise HTTPException(status_code=404, detail="Drift event not found")

    return DriftEventResponse.model_validate(event)


# ---------------------------------------------------------------------------
# GET /drift/servers/{server_id}/timeline
# ---------------------------------------------------------------------------


@router.get("/servers/{server_id}/timeline", response_model=DriftTimelineResponse)
async def get_server_drift_timeline(
    server_id: uuid.UUID,
    hours: int = Query(168, ge=1, le=8760, description="Lookback period in hours (default 7 days)"),
    db: AsyncSession = Depends(get_db),
):
    """Drift timeline for a specific server.

    Returns drift events over the specified time period, suitable for
    timeline visualisation in the frontend.
    """
    monitor = _get_monitor(db)

    try:
        data = await monitor.get_server_drift_timeline(
            server_id=str(server_id),
            hours=hours,
        )
    except Exception as exc:
        logger.error(
            "Failed to fetch drift timeline for server %s: %s",
            server_id, exc, exc_info=True,
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve drift timeline. Please try again later.",
        )

    return DriftTimelineResponse(
        server_request_id=server_id,
        certname=data["certname"],
        period_hours=data["period_hours"],
        events=[
            DriftTimelineEntry(
                id=e.id,
                detected_at=e.detected_at,
                resource_type=e.resource_type,
                resource_title=e.resource_title,
                property_name=e.property_name,
                old_value=e.old_value,
                new_value=e.new_value,
                severity=e.severity,
                is_corrective=e.is_corrective,
                is_resolved=e.is_resolved,
                resolution_type=e.resolution_type,
                drift_category=e.drift_category,
                cis_control_id=e.cis_control_id,
            )
            for e in data["events"]
        ],
        total=data["total"],
    )


# ---------------------------------------------------------------------------
# GET /drift/alerts
# ---------------------------------------------------------------------------


@router.get("/alerts", response_model=DriftAlertListResponse)
async def list_drift_alerts(
    is_acknowledged: bool | None = Query(None, description="Filter by acknowledgment status"),
    severity: str | None = Query(None, description="Filter by severity"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db),
):
    """List drift alerts with filtering and pagination.

    By default returns all alerts. Use ``is_acknowledged=false`` to see
    only active alerts.
    """
    monitor = _get_monitor(db)

    try:
        data = await monitor.get_drift_alerts(
            is_acknowledged=is_acknowledged,
            severity=severity,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        logger.error("Failed to list drift alerts: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to retrieve drift alerts. Please try again later.",
        )

    return DriftAlertListResponse(
        alerts=[DriftAlertResponse.model_validate(a) for a in data["alerts"]],
        total=data["total"],
        page=data["page"],
        page_size=data["page_size"],
    )


# ---------------------------------------------------------------------------
# POST /drift/alerts/{alert_id}/acknowledge
# ---------------------------------------------------------------------------


@router.post("/alerts/{alert_id}/acknowledge", response_model=AcknowledgeAlertResponse)
async def acknowledge_alert(
    alert_id: uuid.UUID,
    body: AcknowledgeAlertRequest,
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge a drift alert.

    Marks the alert as acknowledged with the identity of the person
    acknowledging it and the current timestamp.
    """
    monitor = _get_monitor(db)

    try:
        alert = await monitor.acknowledge_alert(
            alert_id=str(alert_id),
            acknowledged_by=body.acknowledged_by,
        )
    except Exception as exc:
        logger.error(
            "Failed to acknowledge alert %s: %s", alert_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to acknowledge alert. Please try again later.",
        )

    if alert is None:
        raise HTTPException(status_code=404, detail="Drift alert not found")

    return AcknowledgeAlertResponse(
        id=alert.id,
        is_acknowledged=alert.is_acknowledged,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
    )


# ---------------------------------------------------------------------------
# GET /drift/trends
# ---------------------------------------------------------------------------


@router.get("/trends", response_model=DriftTrendsResponse)
async def get_drift_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to trend (default 30)"),
    db: AsyncSession = Depends(get_db),
):
    """Drift trending data over a time period.

    Returns daily event counts broken down by category for chart
    visualisation.
    """
    monitor = _get_monitor(db)

    try:
        data = await monitor.get_drift_trends(days=days)
    except Exception as exc:
        logger.error("Failed to generate drift trends: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Unable to generate drift trends. Please try again later.",
        )

    return DriftTrendsResponse(
        period_days=data["period_days"],
        daily=[DriftTrendDay(**d) for d in data["daily"]],
        generated_at=data["generated_at"],
    )
