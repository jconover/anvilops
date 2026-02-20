"""Pydantic schemas for drift detection API requests and responses."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Drift Event schemas
# ---------------------------------------------------------------------------


class DriftEventBase(BaseModel):
    """Common fields shared by drift event schemas."""

    certname: str
    resource_type: str
    resource_title: str
    property_name: str
    old_value: str | None = None
    new_value: str | None = None
    severity: Literal["critical", "high", "medium", "low"]
    is_corrective: bool = False
    drift_category: Literal[
        "security", "configuration", "package", "service", "file"
    ]
    cis_control_id: str | None = None


class DriftEventResponse(DriftEventBase):
    """A drift event as returned by the API."""

    id: uuid.UUID
    server_request_id: uuid.UUID
    detected_at: datetime
    resolved_at: datetime | None = None
    is_resolved: bool = False
    resolution_type: str | None = None
    report_hash: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DriftEventListResponse(BaseModel):
    """Paginated list of drift events."""

    events: list[DriftEventResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Drift Alert schemas
# ---------------------------------------------------------------------------


class DriftAlertBase(BaseModel):
    """Common fields shared by drift alert schemas."""

    alert_type: Literal["drift_detected", "repeated_drift", "compliance_drop"]
    severity: Literal["critical", "high", "medium", "low"]
    title: str = Field(..., max_length=200)
    message: str


class DriftAlertResponse(DriftAlertBase):
    """A drift alert as returned by the API."""

    id: uuid.UUID
    drift_event_id: uuid.UUID | None = None
    server_request_id: uuid.UUID | None = None
    is_acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DriftAlertListResponse(BaseModel):
    """Paginated list of drift alerts."""

    alerts: list[DriftAlertResponse]
    total: int
    page: int
    page_size: int


class AcknowledgeAlertRequest(BaseModel):
    """Request body for acknowledging a drift alert."""

    acknowledged_by: str = Field(
        ...,
        max_length=255,
        description="Email or username of the person acknowledging the alert",
    )


class AcknowledgeAlertResponse(BaseModel):
    """Response after acknowledging a drift alert."""

    id: uuid.UUID
    is_acknowledged: bool
    acknowledged_by: str
    acknowledged_at: datetime


# ---------------------------------------------------------------------------
# Drift Summary schemas
# ---------------------------------------------------------------------------


class DriftSeverityCount(BaseModel):
    """Count of drift events by severity."""

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


class DriftCategoryCount(BaseModel):
    """Count of drift events by category."""

    security: int = 0
    configuration: int = 0
    package: int = 0
    service: int = 0
    file: int = 0


class DriftSummaryResponse(BaseModel):
    """Fleet-wide drift summary for the dashboard."""

    total_events: int = 0
    unresolved_events: int = 0
    resolved_events: int = 0
    auto_corrected: int = 0
    active_alerts: int = 0
    affected_servers: int = 0
    by_severity: DriftSeverityCount = Field(default_factory=DriftSeverityCount)
    by_category: DriftCategoryCount = Field(default_factory=DriftCategoryCount)
    generated_at: datetime


# ---------------------------------------------------------------------------
# Drift Timeline schemas
# ---------------------------------------------------------------------------


class DriftTimelineEntry(BaseModel):
    """A single entry in a server's drift timeline."""

    id: uuid.UUID
    detected_at: datetime
    resource_type: str
    resource_title: str
    property_name: str
    old_value: str | None = None
    new_value: str | None = None
    severity: str
    is_corrective: bool
    is_resolved: bool
    resolution_type: str | None = None
    drift_category: str
    cis_control_id: str | None = None


class DriftTimelineResponse(BaseModel):
    """Drift timeline for a single server."""

    server_request_id: uuid.UUID
    certname: str
    period_hours: int
    events: list[DriftTimelineEntry]
    total: int


# ---------------------------------------------------------------------------
# Drift Trend schemas
# ---------------------------------------------------------------------------


class DriftTrendDay(BaseModel):
    """Drift event counts for a single day, broken down by category."""

    date: str  # ISO date string (YYYY-MM-DD)
    total: int = 0
    security: int = 0
    configuration: int = 0
    package: int = 0
    service: int = 0
    file: int = 0


class DriftTrendsResponse(BaseModel):
    """Drift trending data over a time period."""

    period_days: int
    daily: list[DriftTrendDay]
    generated_at: datetime
