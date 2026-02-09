"""Pydantic schemas for the scheduled builds API."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ScheduleCreate(BaseModel):
    """Request body for creating a new build schedule."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Human-readable schedule name"
    )
    description: str | None = Field(
        None, max_length=2000, description="Optional description"
    )
    schedule_type: Literal["one_time", "recurring"] = Field(
        ..., description="Whether this is a one-time or recurring schedule"
    )
    scheduled_at: datetime | None = Field(
        None,
        description="When to run (required for one_time schedules, ISO 8601)",
    )
    cron_expression: str | None = Field(
        None,
        max_length=100,
        description="Cron expression for recurring schedules (5-field: min hour dom mon dow)",
    )
    timezone: str = Field(
        "UTC",
        max_length=50,
        description="IANA timezone for the schedule (e.g. 'America/New_York')",
    )
    server_config: dict = Field(
        ..., description="Full ServerCreateRequest payload as a JSON object"
    )
    max_runs: int | None = Field(
        None,
        ge=1,
        description="Maximum number of executions (null = unlimited for recurring)",
    )

    @model_validator(mode="after")
    def validate_schedule_fields(self) -> "ScheduleCreate":
        """Ensure the correct timing fields are provided for each schedule type."""
        if self.schedule_type == "one_time":
            if self.scheduled_at is None:
                raise ValueError(
                    "scheduled_at is required for one_time schedules"
                )
        elif self.schedule_type == "recurring":
            if self.cron_expression is None:
                raise ValueError(
                    "cron_expression is required for recurring schedules"
                )
        return self


class ScheduleUpdate(BaseModel):
    """Request body for updating an existing build schedule."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    scheduled_at: datetime | None = None
    cron_expression: str | None = Field(None, max_length=100)
    timezone: str | None = Field(None, max_length=50)
    server_config: dict | None = None
    max_runs: int | None = Field(None, ge=1)


class ScheduleResponse(BaseModel):
    """Full representation of a build schedule returned by the API."""

    id: uuid.UUID
    name: str
    description: str | None
    status: str
    schedule_type: str
    scheduled_at: datetime | None
    cron_expression: str | None
    timezone: str
    next_run_at: datetime | None
    last_run_at: datetime | None
    run_count: int
    max_runs: int | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleDetailResponse(ScheduleResponse):
    """Schedule with its recent execution history."""

    executions: list["ExecutionResponse"] = []


class ScheduleListResponse(BaseModel):
    """Paginated list of build schedules."""

    schedules: list[ScheduleResponse]
    total: int


class ExecutionResponse(BaseModel):
    """A single execution record for a scheduled build."""

    id: uuid.UUID
    schedule_id: uuid.UUID
    server_request_id: uuid.UUID | None
    status: str
    scheduled_for: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    """Paginated list of schedule executions."""

    executions: list[ExecutionResponse]
    total: int
