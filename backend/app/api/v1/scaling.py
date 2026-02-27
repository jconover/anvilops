"""Auto Scaling Group API endpoints."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.scaling import ScalingGroup, ScalingGroupMember
from app.schemas.scaling import (
    ScaleAction,
    ScalingGroupCreate,
    ScalingGroupListResponse,
    ScalingGroupMemberResponse,
    ScalingGroupResponse,
    ScalingGroupUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# GET /scaling  -- list all scaling groups
# ---------------------------------------------------------------------------


@router.get("/", response_model=ScalingGroupListResponse)
async def list_scaling_groups(
    status: str | None = Query(None, description="Filter by group status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupListResponse:
    """List all scaling groups with optional status filtering."""
    query = select(ScalingGroup)
    count_query = select(func.count(ScalingGroup.id))

    if status:
        query = query.where(ScalingGroup.status == status)
        count_query = count_query.where(ScalingGroup.status == status)

    query = query.order_by(ScalingGroup.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    groups = result.scalars().unique().all()

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    return ScalingGroupListResponse(groups=groups, total=total)


# ---------------------------------------------------------------------------
# GET /scaling/{id}  -- get a single scaling group with members
# ---------------------------------------------------------------------------


@router.get("/{group_id}", response_model=ScalingGroupResponse)
async def get_scaling_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupResponse:
    """Get a specific scaling group with its members."""
    result = await db.execute(
        select(ScalingGroup).where(ScalingGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if group is None:
        raise HTTPException(status_code=404, detail="Scaling group not found")

    return group


# ---------------------------------------------------------------------------
# POST /scaling  -- create a new scaling group
# ---------------------------------------------------------------------------


@router.post("/", response_model=ScalingGroupResponse, status_code=202)
async def create_scaling_group(
    request: ScalingGroupCreate,
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupResponse:
    """Create a new scaling group and trigger initial provisioning.

    After persisting the group configuration, a Celery ``scale_group``
    task is dispatched to provision the ``desired_count`` number of
    servers from the template.
    """
    # Check for duplicate name
    existing = await db.execute(
        select(ScalingGroup).where(ScalingGroup.name == request.name)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Scaling group with name '{request.name}' already exists",
        )

    group = ScalingGroup(
        id=uuid.uuid4(),
        name=request.name,
        description=request.description,
        status="active",
        environment=request.environment,
        os_type=request.os_type,
        instance_size=request.instance_size,
        region=request.region,
        vpc_id=request.vpc_id,
        subnet_id=request.subnet_id,
        security_profile=request.security_profile,
        puppet_role=request.puppet_role,
        min_instances=request.min_instances,
        max_instances=request.max_instances,
        desired_count=request.desired_count,
        current_count=0,
        scale_up_threshold=request.scale_up_threshold,
        scale_down_threshold=request.scale_down_threshold,
        cooldown_seconds=request.cooldown_seconds,
    )

    db.add(group)
    await db.flush()
    await db.refresh(group)

    # Dispatch initial scaling to reach desired_count
    if request.desired_count > 0:
        try:
            from app.tasks.scaling import scale_group

            scale_group.delay(str(group.id), request.desired_count)
        except ImportError:
            logger.warning(
                "Celery scaling task not available; skipping initial dispatch"
            )

    logger.info(
        "Created scaling group '%s' (%s) with desired_count=%d",
        group.name,
        group.id,
        request.desired_count,
    )
    return group


# ---------------------------------------------------------------------------
# PUT /scaling/{id}  -- update scaling group configuration
# ---------------------------------------------------------------------------


@router.put("/{group_id}", response_model=ScalingGroupResponse)
async def update_scaling_group(
    group_id: uuid.UUID,
    request: ScalingGroupUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupResponse:
    """Update a scaling group's configuration.

    Only non-``None`` fields in the request body are applied (partial
    update).  If ``desired_count`` changes and the group is active, a
    ``scale_group`` task is dispatched to reconcile.
    """
    result = await db.execute(
        select(ScalingGroup).where(ScalingGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if group is None:
        raise HTTPException(status_code=404, detail="Scaling group not found")

    if group.status == "deleted":
        raise HTTPException(
            status_code=400, detail="Cannot update a deleted scaling group"
        )

    # Check for name uniqueness if name is being changed
    update_data = request.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"] != group.name:
        existing = await db.execute(
            select(ScalingGroup).where(
                ScalingGroup.name == update_data["name"],
                ScalingGroup.id != group_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Scaling group with name '{update_data['name']}' already exists",
            )

    # Validate cross-field constraints after merging with existing values
    new_min = update_data.get("min_instances", group.min_instances)
    new_max = update_data.get("max_instances", group.max_instances)
    new_desired = update_data.get("desired_count", group.desired_count)

    if new_min > new_max:
        raise HTTPException(
            status_code=422,
            detail=f"min_instances ({new_min}) must be <= max_instances ({new_max})",
        )
    if new_desired < new_min or new_desired > new_max:
        raise HTTPException(
            status_code=422,
            detail=(
                f"desired_count ({new_desired}) must be between "
                f"min_instances ({new_min}) and max_instances ({new_max})"
            ),
        )

    new_up = update_data.get("scale_up_threshold", group.scale_up_threshold)
    new_down = update_data.get("scale_down_threshold", group.scale_down_threshold)
    if new_down >= new_up:
        raise HTTPException(
            status_code=422,
            detail=(
                f"scale_down_threshold ({new_down}) must be "
                f"< scale_up_threshold ({new_up})"
            ),
        )

    # Apply updates
    desired_changed = False
    for field, value in update_data.items():
        if field == "desired_count" and value != group.desired_count:
            desired_changed = True
        setattr(group, field, value)

    await db.flush()
    await db.refresh(group)

    # Trigger reconciliation if desired_count was changed
    if desired_changed and group.status == "active":
        try:
            from app.tasks.scaling import scale_group as scale_group_task

            scale_group_task.delay(str(group.id), group.desired_count)
        except ImportError:
            logger.warning(
                "Celery scaling task not available; skipping dispatch"
            )

    logger.info("Updated scaling group '%s' (%s)", group.name, group.id)
    return group


# ---------------------------------------------------------------------------
# DELETE /scaling/{id}  -- delete group and decommission all members
# ---------------------------------------------------------------------------


@router.delete("/{group_id}", response_model=ScalingGroupResponse)
async def delete_scaling_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupResponse:
    """Delete a scaling group and decommission all its members.

    Marks the group as ``deleted`` and dispatches a ``scale_group`` task
    with ``desired_count=0`` to decommission all active members.
    """
    result = await db.execute(
        select(ScalingGroup).where(ScalingGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if group is None:
        raise HTTPException(status_code=404, detail="Scaling group not found")

    if group.status == "deleted":
        raise HTTPException(
            status_code=400, detail="Scaling group is already deleted"
        )

    group.status = "deleted"
    group.desired_count = 0
    await db.flush()
    await db.refresh(group)

    # Dispatch scale-down to zero to decommission all members
    if group.current_count > 0:
        try:
            from app.tasks.scaling import scale_group as scale_group_task

            scale_group_task.delay(str(group.id), 0)
        except ImportError:
            logger.warning(
                "Celery scaling task not available; skipping decommission dispatch"
            )

    logger.info(
        "Deleted scaling group '%s' (%s); decommissioning %d member(s)",
        group.name,
        group.id,
        group.current_count,
    )
    return group


# ---------------------------------------------------------------------------
# POST /scaling/{id}/scale  -- manual scale action
# ---------------------------------------------------------------------------


@router.post("/{group_id}/scale", response_model=ScalingGroupResponse)
async def manual_scale(
    group_id: uuid.UUID,
    action: ScaleAction,
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupResponse:
    """Manually scale a group to a specific desired count.

    Validates that the requested count is within the group's
    ``[min_instances, max_instances]`` range and dispatches the
    ``scale_group`` Celery task.
    """
    result = await db.execute(
        select(ScalingGroup).where(ScalingGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if group is None:
        raise HTTPException(status_code=404, detail="Scaling group not found")

    if group.status not in ("active", "paused"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot scale a group in '{group.status}' status",
        )

    if action.desired_count < group.min_instances:
        raise HTTPException(
            status_code=422,
            detail=(
                f"desired_count ({action.desired_count}) is below "
                f"min_instances ({group.min_instances})"
            ),
        )
    if action.desired_count > group.max_instances:
        raise HTTPException(
            status_code=422,
            detail=(
                f"desired_count ({action.desired_count}) exceeds "
                f"max_instances ({group.max_instances})"
            ),
        )

    group.desired_count = action.desired_count
    await db.flush()
    await db.refresh(group)

    try:
        from app.tasks.scaling import scale_group as scale_group_task

        scale_group_task.delay(str(group.id), action.desired_count)
    except ImportError:
        logger.warning(
            "Celery scaling task not available; skipping dispatch"
        )

    logger.info(
        "Manual scale requested for group '%s' (%s): desired=%d",
        group.name,
        group.id,
        action.desired_count,
    )
    return group


# ---------------------------------------------------------------------------
# POST /scaling/{id}/pause  -- pause auto-scaling
# ---------------------------------------------------------------------------


@router.post("/{group_id}/pause", response_model=ScalingGroupResponse)
async def pause_scaling_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupResponse:
    """Pause auto-scaling for a group.

    The group's existing members remain running, but the periodic
    ``check_scaling_triggers`` task will skip this group until it is
    resumed.  Manual scaling via ``POST /scaling/{id}/scale`` is still
    allowed while paused.
    """
    result = await db.execute(
        select(ScalingGroup).where(ScalingGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if group is None:
        raise HTTPException(status_code=404, detail="Scaling group not found")

    if group.status == "paused":
        raise HTTPException(
            status_code=400, detail="Scaling group is already paused"
        )

    if group.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Can only pause an active group (current: '{group.status}')",
        )

    group.status = "paused"
    await db.flush()
    await db.refresh(group)

    logger.info("Paused scaling group '%s' (%s)", group.name, group.id)
    return group


# ---------------------------------------------------------------------------
# POST /scaling/{id}/resume  -- resume auto-scaling
# ---------------------------------------------------------------------------


@router.post("/{group_id}/resume", response_model=ScalingGroupResponse)
async def resume_scaling_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ScalingGroupResponse:
    """Resume auto-scaling for a previously paused group."""
    result = await db.execute(
        select(ScalingGroup).where(ScalingGroup.id == group_id)
    )
    group = result.scalar_one_or_none()

    if group is None:
        raise HTTPException(status_code=404, detail="Scaling group not found")

    if group.status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Can only resume a paused group (current: '{group.status}')",
        )

    group.status = "active"
    await db.flush()
    await db.refresh(group)

    logger.info("Resumed scaling group '%s' (%s)", group.name, group.id)
    return group


# ---------------------------------------------------------------------------
# GET /scaling/{id}/members  -- list group members with status
# ---------------------------------------------------------------------------


@router.get("/{group_id}/members", response_model=list[ScalingGroupMemberResponse])
async def list_scaling_group_members(
    group_id: uuid.UUID,
    status: str | None = Query(None, description="Filter by member status"),
    db: AsyncSession = Depends(get_db),
) -> list[ScalingGroupMemberResponse]:
    """List all members of a scaling group with optional status filtering."""
    # Verify group exists
    group_result = await db.execute(
        select(ScalingGroup.id).where(ScalingGroup.id == group_id)
    )
    if group_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Scaling group not found")

    query = (
        select(ScalingGroupMember)
        .where(ScalingGroupMember.scaling_group_id == group_id)
        .order_by(ScalingGroupMember.member_index)
    )

    if status:
        query = query.where(ScalingGroupMember.status == status)

    result = await db.execute(query)
    members = result.scalars().all()

    return members
