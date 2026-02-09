"""Pydantic schemas for Auto Scaling Group API requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Member schemas
# ---------------------------------------------------------------------------


class ScalingGroupMemberResponse(BaseModel):
    """Read-only representation of a single scaling group member."""

    id: uuid.UUID
    scaling_group_id: uuid.UUID
    server_request_id: uuid.UUID | None = None
    member_index: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------


class ScalingGroupCreate(BaseModel):
    """Payload for creating a new scaling group."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    environment: str = Field(..., min_length=1, max_length=20)
    os_type: str = Field(..., min_length=1, max_length=50)
    instance_size: str = Field(..., min_length=1, max_length=20)
    region: str = Field(..., min_length=1, max_length=20)
    vpc_id: str = Field(..., min_length=1, max_length=50)
    subnet_id: str = Field(..., min_length=1, max_length=50)
    security_profile: str = Field("internal_only", max_length=20)
    puppet_role: str = Field("base", max_length=50)
    min_instances: int = Field(1, ge=1, le=20)
    max_instances: int = Field(5, ge=1, le=20)
    desired_count: int = Field(1, ge=1, le=20)
    scale_up_threshold: int = Field(80, ge=50, le=100)
    scale_down_threshold: int = Field(20, ge=5, le=50)
    cooldown_seconds: int = Field(300, ge=60, le=3600)

    @model_validator(mode="after")
    def validate_instance_counts(self) -> "ScalingGroupCreate":
        if self.min_instances > self.max_instances:
            raise ValueError(
                f"min_instances ({self.min_instances}) must be "
                f"<= max_instances ({self.max_instances})"
            )
        if self.desired_count < self.min_instances:
            raise ValueError(
                f"desired_count ({self.desired_count}) must be "
                f">= min_instances ({self.min_instances})"
            )
        if self.desired_count > self.max_instances:
            raise ValueError(
                f"desired_count ({self.desired_count}) must be "
                f"<= max_instances ({self.max_instances})"
            )
        if self.scale_down_threshold >= self.scale_up_threshold:
            raise ValueError(
                f"scale_down_threshold ({self.scale_down_threshold}) must be "
                f"< scale_up_threshold ({self.scale_up_threshold})"
            )
        return self


class ScalingGroupUpdate(BaseModel):
    """Partial update payload for an existing scaling group."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    min_instances: int | None = Field(None, ge=1, le=20)
    max_instances: int | None = Field(None, ge=1, le=20)
    desired_count: int | None = Field(None, ge=1, le=20)
    scale_up_threshold: int | None = Field(None, ge=50, le=100)
    scale_down_threshold: int | None = Field(None, ge=5, le=50)
    cooldown_seconds: int | None = Field(None, ge=60, le=3600)
    security_profile: str | None = Field(None, max_length=20)
    puppet_role: str | None = Field(None, max_length=50)


class ScaleAction(BaseModel):
    """Payload for a manual scale action."""

    desired_count: int = Field(..., ge=1, le=20)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class ScalingGroupResponse(BaseModel):
    """Full representation of a scaling group, including members."""

    id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    environment: str
    os_type: str
    instance_size: str
    region: str
    vpc_id: str
    subnet_id: str
    security_profile: str
    puppet_role: str
    min_instances: int
    max_instances: int
    desired_count: int
    current_count: int
    scale_up_threshold: int
    scale_down_threshold: int
    cooldown_seconds: int
    last_scaled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    members: list[ScalingGroupMemberResponse] = []

    model_config = {"from_attributes": True}


class ScalingGroupListResponse(BaseModel):
    """Paginated list of scaling groups."""

    groups: list[ScalingGroupResponse]
    total: int
