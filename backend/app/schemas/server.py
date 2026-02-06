"""Pydantic schemas for server API requests and responses."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StorageConfig(BaseModel):
    drive_letter: str | None = Field(None, description="Drive letter (Windows)")
    mount_point: str | None = Field(None, description="Mount point (Linux)")
    size_gb: int = Field(..., ge=1, le=16384, description="Volume size in GB")
    volume_type: Literal["gp3", "io2"] = "gp3"


class ServerCreateRequest(BaseModel):
    server_name: str | None = Field(None, description="Auto-generated if not provided")
    environment: Literal["dev", "staging", "production"]
    os_type: Literal[
        "windows_2022", "windows_2019",
        "amazon_linux_2023", "ubuntu_2204", "rhel_9"
    ]
    instance_size: Literal["small", "medium", "large", "xl"]
    region: str = "us-east-1"
    vpc_id: str
    subnet_id: str
    security_profile: Literal[
        "web_facing", "internal_only", "database", "custom"
    ] = "internal_only"
    domain_join: bool = False
    software_packages: list[str] = []
    puppet_role: str = "base"
    additional_storage: list[StorageConfig] = []
    tags: dict[str, str] = {}
    template_id: str | None = None


class ServerResponse(BaseModel):
    id: uuid.UUID
    server_name: str
    environment: str
    os_type: str
    instance_size: str
    region: str
    status: str
    status_message: str | None = None
    aws_instance_id: str | None = None
    private_ip: str | None = None
    public_ip: str | None = None
    dns_name: str | None = None
    awx_host_id: int | None = None
    awx_job_ids: list | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ServerListResponse(BaseModel):
    servers: list[ServerResponse]
    total: int
