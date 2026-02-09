"""Pydantic schemas for CMDB API requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CMDBSyncStatusResponse(BaseModel):
    """CMDB sync status for a single server."""

    server_id: uuid.UUID
    server_name: str
    cmdb_sys_id: str | None = None
    cmdb_synced: bool = Field(
        description="Whether the server has a CMDB CI record"
    )
    cmdb_ci: dict | None = Field(
        None,
        description="Full CI record from ServiceNow (if available)",
    )
    relationships: list[dict] = Field(
        default_factory=list,
        description="CI relationships from ServiceNow",
    )


class CMDBSyncTriggerResponse(BaseModel):
    """Response from triggering a manual CMDB sync for a server."""

    server_id: uuid.UUID
    server_name: str
    task_id: str = Field(description="Celery task ID for tracking")
    message: str


class CMDBFullSyncResponse(BaseModel):
    """Response from triggering a full CMDB reconciliation."""

    task_id: str = Field(description="Celery task ID for tracking")
    message: str


class CMDBSyncStatsResponse(BaseModel):
    """CMDB synchronization statistics."""

    total_servers: int = Field(description="Total server count in AnvilOps")
    synced: int = Field(
        description="Servers with a cmdb_sys_id (synced to CMDB)"
    )
    unsynced: int = Field(
        description="Servers without a cmdb_sys_id (not yet synced)"
    )
    by_status: dict[str, int] = Field(
        description="Server counts grouped by status"
    )
    servicenow_enabled: bool = Field(
        description="Whether ServiceNow integration is enabled"
    )
    servicenow_instance: str = Field(
        description="ServiceNow instance URL (masked)"
    )
