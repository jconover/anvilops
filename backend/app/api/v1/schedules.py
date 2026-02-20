"""Scheduled builds API endpoints.

Provides CRUD operations for build schedules plus lifecycle actions
(pause, resume, run-now) and execution history queries.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.schedule import BuildSchedule, ScheduleExecution
from app.schemas.schedule import (
    ExecutionListResponse,
    ExecutionResponse,
    ScheduleCreate,
    ScheduleDetailResponse,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdate,
)
from app.services.cron_parser import get_next_run, validate_cron

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_next_run(schedule: BuildSchedule) -> datetime | None:
    """Compute the next_run_at value for a schedule.

    Returns ``None`` when the schedule should not run again (e.g.,
    one-time schedule already executed, or max_runs reached).
    """
    now = datetime.now(timezone.utc)

    if schedule.schedule_type == "one_time":
        if schedule.run_count > 0:
            return None
        return schedule.scheduled_at

    # Recurring
    if schedule.max_runs is not None and schedule.run_count >= schedule.max_runs:
        return None

    if schedule.cron_expression is None:
        return None

    reference = schedule.last_run_at or now
    try:
        return get_next_run(
            schedule.cron_expression,
            after=reference,
            timezone=schedule.timezone or "UTC",
        )
    except (ValueError, KeyError):
        logger.warning(
            "Failed to compute next_run_at for schedule %s with cron=%r tz=%r",
            schedule.id,
            schedule.cron_expression,
            schedule.timezone,
        )
        return None


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=ScheduleResponse, status_code=201)
async def create_schedule(
    request: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new build schedule.

    For ``one_time`` schedules, ``scheduled_at`` is required.
    For ``recurring`` schedules, ``cron_expression`` is required and
    must be a valid 5-field cron string.
    """
    # Validate cron expression if recurring
    if request.schedule_type == "recurring" and request.cron_expression:
        if not validate_cron(request.cron_expression):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid cron expression: {request.cron_expression!r}",
            )

    # Validate scheduled_at is in the future for one_time
    if request.schedule_type == "one_time" and request.scheduled_at:
        now = datetime.now(timezone.utc)
        scheduled_utc = request.scheduled_at
        if scheduled_utc.tzinfo is None:
            scheduled_utc = scheduled_utc.replace(tzinfo=timezone.utc)
        if scheduled_utc <= now:
            raise HTTPException(
                status_code=422,
                detail="scheduled_at must be in the future",
            )

    schedule = BuildSchedule(
        id=uuid.uuid4(),
        name=request.name,
        description=request.description,
        status="active",
        schedule_type=request.schedule_type,
        scheduled_at=request.scheduled_at,
        cron_expression=request.cron_expression,
        timezone=request.timezone,
        server_config=request.server_config,
        max_runs=request.max_runs,
        run_count=0,
        created_by=None,  # TODO: populate from auth context
    )

    # Compute initial next_run_at
    schedule.next_run_at = _compute_next_run(schedule)

    db.add(schedule)
    await db.flush()
    await db.refresh(schedule)

    logger.info(
        "Created build schedule: %s (%s) type=%s next_run=%s",
        schedule.name,
        schedule.id,
        schedule.schedule_type,
        schedule.next_run_at,
    )
    return schedule


@router.get("/", response_model=ScheduleListResponse)
async def list_schedules(
    status: str | None = Query(None, description="Filter by status"),
    schedule_type: str | None = Query(None, description="Filter by type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List all build schedules with optional filtering."""
    query = select(BuildSchedule)
    count_query = select(func.count(BuildSchedule.id))

    if status:
        query = query.where(BuildSchedule.status == status)
        count_query = count_query.where(BuildSchedule.status == status)
    if schedule_type:
        query = query.where(BuildSchedule.schedule_type == schedule_type)
        count_query = count_query.where(BuildSchedule.schedule_type == schedule_type)

    query = query.order_by(BuildSchedule.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    schedules = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return ScheduleListResponse(schedules=schedules, total=total)


@router.get("/{schedule_id}", response_model=ScheduleDetailResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific build schedule with its recent execution history."""
    result = await db.execute(
        select(BuildSchedule).where(BuildSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: uuid.UUID,
    request: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing build schedule.

    Only ``active`` or ``paused`` schedules can be updated.  Completed
    and cancelled schedules are immutable.
    """
    result = await db.execute(
        select(BuildSchedule).where(BuildSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    if schedule.status in ("completed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update a {schedule.status} schedule",
        )

    # Apply partial updates
    if request.name is not None:
        schedule.name = request.name
    if request.description is not None:
        schedule.description = request.description
    if request.scheduled_at is not None:
        schedule.scheduled_at = request.scheduled_at
    if request.cron_expression is not None:
        if not validate_cron(request.cron_expression):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid cron expression: {request.cron_expression!r}",
            )
        schedule.cron_expression = request.cron_expression
    if request.timezone is not None:
        schedule.timezone = request.timezone
    if request.server_config is not None:
        schedule.server_config = request.server_config
    if request.max_runs is not None:
        schedule.max_runs = request.max_runs

    # Recompute next_run_at after any timing-related changes
    schedule.next_run_at = _compute_next_run(schedule)
    schedule.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(schedule)

    logger.info("Updated build schedule: %s (%s)", schedule.name, schedule.id)
    return schedule


@router.delete("/{schedule_id}", response_model=ScheduleResponse)
async def delete_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel and soft-delete a build schedule.

    Sets the schedule status to ``cancelled`` and clears
    ``next_run_at`` so the periodic task will no longer pick it up.
    The record is preserved for audit purposes.
    """
    result = await db.execute(
        select(BuildSchedule).where(BuildSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    if schedule.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail="Schedule is already cancelled",
        )

    schedule.status = "cancelled"
    schedule.next_run_at = None
    schedule.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(schedule)

    logger.info("Cancelled build schedule: %s (%s)", schedule.name, schedule.id)
    return schedule


# ---------------------------------------------------------------------------
# Lifecycle Actions
# ---------------------------------------------------------------------------


@router.post("/{schedule_id}/pause", response_model=ScheduleResponse)
async def pause_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Pause an active schedule.

    The schedule retains its configuration but ``next_run_at`` is
    cleared so the periodic task will skip it until it is resumed.
    """
    result = await db.execute(
        select(BuildSchedule).where(BuildSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    if schedule.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Only active schedules can be paused (current: {schedule.status})",
        )

    schedule.status = "paused"
    schedule.next_run_at = None
    schedule.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(schedule)

    logger.info("Paused build schedule: %s (%s)", schedule.name, schedule.id)
    return schedule


@router.post("/{schedule_id}/resume", response_model=ScheduleResponse)
async def resume_schedule(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Resume a paused schedule.

    Re-computes ``next_run_at`` from the current time and restores
    the schedule to ``active`` status.
    """
    result = await db.execute(
        select(BuildSchedule).where(BuildSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    if schedule.status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Only paused schedules can be resumed (current: {schedule.status})",
        )

    schedule.status = "active"
    schedule.next_run_at = _compute_next_run(schedule)
    schedule.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(schedule)

    logger.info("Resumed build schedule: %s (%s)", schedule.name, schedule.id)
    return schedule


@router.post("/{schedule_id}/run-now", response_model=ExecutionResponse, status_code=202)
async def run_schedule_now(
    schedule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Trigger an immediate execution of a schedule.

    Creates a new ScheduleExecution with ``scheduled_for`` set to now
    and dispatches the Celery task.  Does not affect the regular
    schedule cadence.
    """
    result = await db.execute(
        select(BuildSchedule).where(BuildSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    if schedule.status in ("cancelled", "completed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run a {schedule.status} schedule",
        )

    now = datetime.now(timezone.utc)

    execution = ScheduleExecution(
        id=uuid.uuid4(),
        schedule_id=schedule.id,
        status="pending",
        scheduled_for=now,
    )
    db.add(execution)
    await db.flush()
    await db.refresh(execution)

    # Dispatch Celery task
    try:
        from app.tasks.scheduler import execute_scheduled_build
        execute_scheduled_build.delay(str(schedule.id), str(execution.id))
    except ImportError:
        logger.warning("Celery scheduler tasks not yet available, skipping dispatch")

    logger.info(
        "Triggered immediate execution for schedule %s (%s), execution %s",
        schedule.name,
        schedule.id,
        execution.id,
    )
    return execution


# ---------------------------------------------------------------------------
# Execution History
# ---------------------------------------------------------------------------


@router.get("/{schedule_id}/executions", response_model=ExecutionListResponse)
async def list_executions(
    schedule_id: uuid.UUID,
    status: str | None = Query(None, description="Filter by execution status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List execution history for a specific schedule."""
    # Verify the schedule exists
    sched_result = await db.execute(
        select(BuildSchedule.id).where(BuildSchedule.id == schedule_id)
    )
    if sched_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Build schedule not found")

    query = select(ScheduleExecution).where(
        ScheduleExecution.schedule_id == schedule_id
    )
    count_query = select(func.count(ScheduleExecution.id)).where(
        ScheduleExecution.schedule_id == schedule_id
    )

    if status:
        query = query.where(ScheduleExecution.status == status)
        count_query = count_query.where(ScheduleExecution.status == status)

    query = (
        query.order_by(ScheduleExecution.scheduled_for.desc())
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    executions = result.scalars().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    return ExecutionListResponse(executions=executions, total=total)
