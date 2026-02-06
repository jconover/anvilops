"""Pydantic schemas for notification API requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    """Single notification returned to the client."""

    id: uuid.UUID
    title: str
    message: str
    category: str
    severity: str
    is_read: bool
    read_at: datetime | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    action_url: str | None = None
    icon: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    """Paginated list of notifications with unread count."""

    notifications: list[NotificationResponse]
    total: int
    unread_count: int


class NotificationMarkReadRequest(BaseModel):
    """Request body to mark specific notifications as read."""

    notification_ids: list[uuid.UUID] = Field(
        ..., min_length=1, description="IDs of notifications to mark as read"
    )


class NotificationDeleteResponse(BaseModel):
    """Confirmation of a deleted notification."""

    detail: str
