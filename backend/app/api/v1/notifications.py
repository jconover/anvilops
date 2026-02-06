"""Notification API endpoints.

Provides CRUD-style access to in-app notifications.  Since auth is
currently mocked, the user is identified via a ``user_email`` query
parameter (defaults to ``"all"`` so every notification is visible).
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationDeleteResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_USER = "all"


def _user_filter(user_email: str):
    """Return a SQLAlchemy filter matching the given user or broadcasts."""
    return or_(
        Notification.user_email == user_email,
        Notification.user_email == "all",
    )


# ------------------------------------------------------------------
# GET /notifications
# ------------------------------------------------------------------


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    user_email: str = Query(DEFAULT_USER, description="Recipient email"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    category: str | None = Query(None, description="Filter by category"),
    is_read: bool | None = Query(None, description="Filter by read status"),
    severity: str | None = Query(None, description="Filter by severity"),
    db: AsyncSession = Depends(get_db),
):
    """List notifications for the current user, newest first."""
    base_filter = _user_filter(user_email)

    # Build query
    query = select(Notification).where(base_filter)
    count_query = select(func.count(Notification.id)).where(base_filter)

    if category is not None:
        query = query.where(Notification.category == category)
        count_query = count_query.where(Notification.category == category)
    if is_read is not None:
        query = query.where(Notification.is_read == is_read)
        count_query = count_query.where(Notification.is_read == is_read)
    if severity is not None:
        query = query.where(Notification.severity == severity)
        count_query = count_query.where(Notification.severity == severity)

    offset = (page - 1) * page_size
    query = (
        query
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    notifications = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Unread count (always unfiltered by category/severity for the badge)
    unread_result = await db.execute(
        select(func.count(Notification.id)).where(
            base_filter,
            Notification.is_read == False,  # noqa: E712
        )
    )
    unread_count = unread_result.scalar()

    return NotificationListResponse(
        notifications=notifications,
        total=total,
        unread_count=unread_count,
    )


# ------------------------------------------------------------------
# GET /notifications/unread-count
# ------------------------------------------------------------------


@router.get("/unread-count")
async def get_unread_count(
    user_email: str = Query(DEFAULT_USER, description="Recipient email"),
    db: AsyncSession = Depends(get_db),
):
    """Return the number of unread notifications for the user."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            _user_filter(user_email),
            Notification.is_read == False,  # noqa: E712
        )
    )
    return {"unread_count": result.scalar()}


# ------------------------------------------------------------------
# POST /notifications/mark-read
# ------------------------------------------------------------------


@router.post("/mark-read", response_model=list[NotificationResponse])
async def mark_read(
    body: NotificationMarkReadRequest,
    user_email: str = Query(DEFAULT_USER, description="Recipient email"),
    db: AsyncSession = Depends(get_db),
):
    """Mark specific notifications as read."""
    now = datetime.now(timezone.utc)

    await db.execute(
        update(Notification)
        .where(
            Notification.id.in_(body.notification_ids),
            _user_filter(user_email),
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, read_at=now)
    )

    # Return updated notifications
    result = await db.execute(
        select(Notification).where(
            Notification.id.in_(body.notification_ids),
            _user_filter(user_email),
        )
    )
    return result.scalars().all()


# ------------------------------------------------------------------
# POST /notifications/mark-all-read
# ------------------------------------------------------------------


@router.post("/mark-all-read")
async def mark_all_read(
    user_email: str = Query(DEFAULT_USER, description="Recipient email"),
    db: AsyncSession = Depends(get_db),
):
    """Mark every unread notification for the user as read."""
    now = datetime.now(timezone.utc)

    result = await db.execute(
        update(Notification)
        .where(
            _user_filter(user_email),
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, read_at=now)
    )

    count = result.rowcount
    logger.info("Marked %d notifications as read for %s", count, user_email)
    return {"marked_read": count}


# ------------------------------------------------------------------
# DELETE /notifications/{notification_id}
# ------------------------------------------------------------------


@router.delete(
    "/{notification_id}", response_model=NotificationDeleteResponse
)
async def delete_notification(
    notification_id: uuid.UUID,
    user_email: str = Query(DEFAULT_USER, description="Recipient email"),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            _user_filter(user_email),
        )
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.delete(notification)
    await db.flush()

    logger.info("Deleted notification %s", notification_id)
    return NotificationDeleteResponse(detail="Notification deleted")
