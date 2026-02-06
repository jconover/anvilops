"""Pydantic schemas for audit log API requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """Single audit log entry returned by the API."""

    id: uuid.UUID
    timestamp: datetime
    action: str
    category: str
    actor_email: str | None = None
    actor_role: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    resource_name: str | None = None
    details: dict | None = None
    ip_address: str | None = None
    status: str
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    logs: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AuditQueryParams(BaseModel):
    """Query parameters for filtering and paginating audit logs."""

    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(50, ge=1, le=500, description="Results per page")
    action: str | None = Field(None, description="Filter by action (e.g. server.created)")
    category: str | None = Field(None, description="Filter by category (e.g. server, auth)")
    actor_email: str | None = Field(None, description="Filter by actor email")
    resource_id: str | None = Field(None, description="Filter by resource UUID")
    start_date: datetime | None = Field(None, description="Include logs on or after this timestamp")
    end_date: datetime | None = Field(None, description="Include logs on or before this timestamp")
    status: str | None = Field(None, description="Filter by outcome status (success, failure, error)")


class AuditDailyCounts(BaseModel):
    """Audit events aggregated by day."""

    date: str
    count: int


class AuditActionCount(BaseModel):
    """Count of events for a specific action type."""

    action: str
    count: int


class AuditActorCount(BaseModel):
    """Count of events for a specific actor."""

    actor_email: str
    count: int


class AuditSummaryResponse(BaseModel):
    """Aggregate statistics for the audit dashboard."""

    daily_counts: list[AuditDailyCounts]
    top_actions: list[AuditActionCount]
    top_actors: list[AuditActorCount]
    total_events: int
