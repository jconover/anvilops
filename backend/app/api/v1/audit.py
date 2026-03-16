"""Audit log query endpoints.

Provides read-only access to the audit trail for compliance dashboards,
admin investigation, and filter-driven log exploration.

All endpoints require authentication (to be enforced once Cognito RBAC
is wired up). In the future, only Admins and Viewers will be permitted.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.db.session import get_db
from app.models.audit import AuditLog
from app.schemas.audit import (
    AuditActionCount,
    AuditActorCount,
    AuditDailyCounts,
    AuditLogListResponse,
    AuditLogResponse,
    AuditSummaryResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/actions", response_model=list[str])
async def list_audit_actions(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return all distinct action types recorded in the audit log.

    Useful for populating filter dropdowns in the frontend.
    """
    result = await db.execute(
        select(AuditLog.action)
        .distinct()
        .order_by(AuditLog.action)
    )
    actions = result.scalars().all()
    return actions


@router.get("/summary", response_model=AuditSummaryResponse)
async def audit_summary(
    user: CurrentUser,
    days: int = Query(30, ge=1, le=365, description="Number of days to look back"),
    db: AsyncSession = Depends(get_db),
) -> AuditSummaryResponse:
    """Aggregate audit statistics for dashboards.

    Returns:
    - Daily event counts for the requested period.
    - Top 10 most frequent actions.
    - Top 10 most active actors.
    - Total event count for the period.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # --- Daily counts ---
    daily_q = (
        select(
            cast(AuditLog.timestamp, Date).label("day"),
            func.count().label("cnt"),
        )
        .where(AuditLog.timestamp >= since)
        .group_by("day")
        .order_by("day")
    )
    daily_result = await db.execute(daily_q)
    daily_counts = [
        AuditDailyCounts(date=str(row.day), count=row.cnt)
        for row in daily_result.all()
    ]

    # --- Top actions ---
    actions_q = (
        select(
            AuditLog.action,
            func.count().label("cnt"),
        )
        .where(AuditLog.timestamp >= since)
        .group_by(AuditLog.action)
        .order_by(func.count().desc())
        .limit(10)
    )
    actions_result = await db.execute(actions_q)
    top_actions = [
        AuditActionCount(action=row.action, count=row.cnt)
        for row in actions_result.all()
    ]

    # --- Top actors ---
    actors_q = (
        select(
            AuditLog.actor_email,
            func.count().label("cnt"),
        )
        .where(AuditLog.timestamp >= since)
        .where(AuditLog.actor_email.is_not(None))
        .group_by(AuditLog.actor_email)
        .order_by(func.count().desc())
        .limit(10)
    )
    actors_result = await db.execute(actors_q)
    top_actors = [
        AuditActorCount(actor_email=row.actor_email, count=row.cnt)
        for row in actors_result.all()
    ]

    # --- Total count ---
    total_q = (
        select(func.count())
        .select_from(AuditLog)
        .where(AuditLog.timestamp >= since)
    )
    total_result = await db.execute(total_q)
    total_events = total_result.scalar() or 0

    return AuditSummaryResponse(
        daily_counts=daily_counts,
        top_actions=top_actions,
        top_actors=top_actors,
        total_events=total_events,
    )


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    action: str | None = Query(None, description="Filter by action"),
    category: str | None = Query(None, description="Filter by category"),
    actor_email: str | None = Query(None, description="Filter by actor email"),
    resource_id: str | None = Query(None, description="Filter by resource UUID"),
    start_date: datetime | None = Query(
        None, description="Include logs on or after this timestamp"
    ),
    end_date: datetime | None = Query(
        None, description="Include logs on or before this timestamp"
    ),
    status: str | None = Query(None, description="Filter by outcome status"),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """List audit logs with pagination and optional filters.

    Returns newest entries first. All filter parameters are optional
    and can be combined.
    """
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)

    # Apply filters
    if action is not None:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if category is not None:
        query = query.where(AuditLog.category == category)
        count_query = count_query.where(AuditLog.category == category)
    if actor_email is not None:
        query = query.where(AuditLog.actor_email == actor_email)
        count_query = count_query.where(AuditLog.actor_email == actor_email)
    if resource_id is not None:
        query = query.where(AuditLog.resource_id == resource_id)
        count_query = count_query.where(AuditLog.resource_id == resource_id)
    if start_date is not None:
        query = query.where(AuditLog.timestamp >= start_date)
        count_query = count_query.where(AuditLog.timestamp >= start_date)
    if end_date is not None:
        query = query.where(AuditLog.timestamp <= end_date)
        count_query = count_query.where(AuditLog.timestamp <= end_date)
    if status is not None:
        query = query.where(AuditLog.status == status)
        count_query = count_query.where(AuditLog.status == status)

    # Paginate (newest first)
    offset = (page - 1) * page_size
    query = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return AuditLogListResponse(
        logs=logs,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    user: CurrentUser,
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """Get a single audit log entry by ID."""
    result = await db.execute(
        select(AuditLog).where(AuditLog.id == audit_id)
    )
    log_entry = result.scalar_one_or_none()

    if log_entry is None:
        raise HTTPException(status_code=404, detail="Audit log entry not found")

    return log_entry
