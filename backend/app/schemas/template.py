"""Pydantic schemas for the server template catalog API."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TemplateCreate(BaseModel):
    """Schema for creating a new server template."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    icon: str = "server"
    is_active: bool = True
    sort_order: int = 0
    os_type: str = Field(..., min_length=1, max_length=50)
    instance_size: str = Field(..., min_length=1, max_length=20)
    region: str = "us-east-1"
    security_profile: str = "internal_only"
    puppet_role: str = "base"
    domain_join: bool = False
    software_packages: list[str] = []
    additional_storage: list[dict] = []
    default_tags: dict[str, str] = {}


class TemplateUpdate(BaseModel):
    """Schema for partially updating an existing template.

    All fields are optional; only provided fields are applied.
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    icon: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    os_type: str | None = Field(None, min_length=1, max_length=50)
    instance_size: str | None = Field(None, min_length=1, max_length=20)
    region: str | None = None
    security_profile: str | None = None
    puppet_role: str | None = None
    domain_join: bool | None = None
    software_packages: list[str] | None = None
    additional_storage: list[dict] | None = None
    default_tags: dict[str, str] | None = None


class TemplateResponse(BaseModel):
    """Schema for a single template returned from the API."""

    id: uuid.UUID
    name: str
    description: str | None
    icon: str
    is_active: bool
    sort_order: int
    os_type: str
    instance_size: str
    region: str
    security_profile: str
    puppet_role: str
    domain_join: bool
    software_packages: list[str]
    additional_storage: list[dict]
    default_tags: dict[str, str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TemplateListResponse(BaseModel):
    """Paginated list of templates."""

    templates: list[TemplateResponse]
    total: int
