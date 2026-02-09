"""
Celery tasks for Auto Scaling Group operations.

``scale_group`` -- scales a specific group to a desired count.
``check_scaling_triggers`` -- periodic task that evaluates all active groups
against their scaling policies and triggers adjustments.
"""

import logging
import uuid
from datetime import datetime, timezone, timedelta

from app.worker.celery_app import celery_app
from app.services.db import get_sync_db
from app.models.scaling import ScalingGroup, ScalingGroupMember
from app.services.scaling import ScalingService

logger = logging.getLogger(__name__)

scaling_service = ScalingService()


# ---------------------------------------------------------------------------
# Task: scale a single group to a desired count
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="tasks.scale_group", max_retries=2)
def scale_group(self, scaling_group_id: str, desired_count: int) -> dict:
    """Scale a group to the desired count.

    If ``desired_count`` > ``current_count``: create new servers using the
    group template configuration.
    If ``desired_count`` < ``current_count``: decommission excess servers
    (newest first).

    Args:
        scaling_group_id: UUID string of the ``ScalingGroup``.
        desired_count: Target number of active members.

    Returns:
        Dict with ``status``, ``scaling_group_id``, ``previous_count``,
        ``desired_count``, and ``actions_taken``.
    """
    logger.info(
        "scale_group task started: group=%s desired=%d",
        scaling_group_id,
        desired_count,
    )

    actions: list[dict] = []

    with get_sync_db() as session:
        group = session.get(ScalingGroup, scaling_group_id)
        if group is None:
            logger.error("ScalingGroup not found: %s", scaling_group_id)
            return {
                "status": "error",
                "scaling_group_id": scaling_group_id,
                "error": f"ScalingGroup not found: {scaling_group_id}",
            }

        if group.status not in ("active", "scaling"):
            logger.warning(
                "ScalingGroup %s is in status '%s'; refusing to scale",
                scaling_group_id,
                group.status,
            )
            return {
                "status": "skipped",
                "scaling_group_id": scaling_group_id,
                "reason": f"Group status is '{group.status}'",
            }

        # Clamp desired count within configured bounds
        desired_count = max(group.min_instances, min(desired_count, group.max_instances))

        previous_count = group.current_count
        group.status = "scaling"
        group.desired_count = desired_count
        group.updated_at = datetime.now(timezone.utc)
        session.flush()

    # ------------------------------------------------------------------
    # Scale UP: create new members
    # ------------------------------------------------------------------
    if desired_count > previous_count:
        members_to_add = desired_count - previous_count
        logger.info(
            "Scaling UP group %s: adding %d member(s) (%d -> %d)",
            scaling_group_id,
            members_to_add,
            previous_count,
            desired_count,
        )

        for _ in range(members_to_add):
            try:
                with get_sync_db() as session:
                    idx = scaling_service.get_next_member_index(
                        session, scaling_group_id
                    )
                    sr_id = scaling_service.create_group_member(
                        session, scaling_group_id, idx
                    )
                    actions.append({
                        "action": "create",
                        "member_index": idx,
                        "server_request_id": sr_id,
                    })
            except Exception as exc:
                logger.exception(
                    "Failed to create member for group %s: %s",
                    scaling_group_id,
                    exc,
                )
                actions.append({
                    "action": "create",
                    "error": str(exc)[:500],
                })

    # ------------------------------------------------------------------
    # Scale DOWN: remove newest members
    # ------------------------------------------------------------------
    elif desired_count < previous_count:
        members_to_remove = previous_count - desired_count
        logger.info(
            "Scaling DOWN group %s: removing %d member(s) (%d -> %d)",
            scaling_group_id,
            members_to_remove,
            previous_count,
            desired_count,
        )

        with get_sync_db() as session:
            removable = scaling_service.get_removable_members(
                session, scaling_group_id, members_to_remove
            )

            for member in removable:
                try:
                    scaling_service.remove_group_member(
                        session, scaling_group_id, str(member.id)
                    )
                    actions.append({
                        "action": "remove",
                        "member_id": str(member.id),
                        "member_index": member.member_index,
                    })
                except Exception as exc:
                    logger.exception(
                        "Failed to remove member %s from group %s: %s",
                        member.id,
                        scaling_group_id,
                        exc,
                    )
                    actions.append({
                        "action": "remove",
                        "member_id": str(member.id),
                        "error": str(exc)[:500],
                    })

    else:
        logger.info(
            "Group %s is already at desired count %d; nothing to do",
            scaling_group_id,
            desired_count,
        )

    # ------------------------------------------------------------------
    # Finalize: update group status back to active
    # ------------------------------------------------------------------
    with get_sync_db() as session:
        group = session.get(ScalingGroup, scaling_group_id)
        if group is not None:
            group.status = "active"
            group.last_scaled_at = datetime.now(timezone.utc)
            group.updated_at = datetime.now(timezone.utc)
            # Recount active members to stay accurate
            group.current_count = (
                session.query(ScalingGroupMember)
                .filter(
                    ScalingGroupMember.scaling_group_id == uuid.UUID(scaling_group_id),
                    ScalingGroupMember.status == "active",
                )
                .count()
            )

    logger.info(
        "scale_group completed: group=%s previous=%d desired=%d actions=%d",
        scaling_group_id,
        previous_count,
        desired_count,
        len(actions),
    )

    return {
        "status": "completed",
        "scaling_group_id": scaling_group_id,
        "previous_count": previous_count,
        "desired_count": desired_count,
        "actions_taken": actions,
    }


# ---------------------------------------------------------------------------
# Periodic task: evaluate all active groups
# ---------------------------------------------------------------------------


def _get_group_metrics(group_id: str) -> dict:
    """Fetch current metrics for a scaling group.

    In a production deployment this would query CloudWatch or a metrics
    aggregator for average CPU, memory, and network utilisation across all
    active members. For the demo/prototype this returns a stub that keeps
    groups at their current size (avg_cpu=50 is within most default
    thresholds).

    Args:
        group_id: UUID string of the scaling group.

    Returns:
        Dict with ``avg_cpu`` (float, 0-100).
    """
    # TODO: Replace with real CloudWatch / Prometheus query
    logger.debug("Fetching metrics for group %s (stub)", group_id)
    return {"avg_cpu": 50.0}


@celery_app.task(name="tasks.check_scaling_triggers")
def check_scaling_triggers() -> dict:
    """Periodic task to check all active groups against scaling policies.

    Intended to be called by Celery Beat every 60 seconds.  For each
    active (non-paused, non-deleted) group that is past its cooldown
    period, the task:

    1. Fetches current metrics (CPU utilisation).
    2. Calculates the desired count using ``ScalingService``.
    3. If the desired count differs from the current count, dispatches
       a ``scale_group`` task.

    Returns:
        Dict with ``evaluated`` count, ``scaled`` count, and per-group
        details.
    """
    logger.info("check_scaling_triggers: starting evaluation")

    evaluated = 0
    scaled = 0
    details: list[dict] = []

    with get_sync_db() as session:
        groups = (
            session.query(ScalingGroup)
            .filter(ScalingGroup.status == "active")
            .all()
        )

        now = datetime.now(timezone.utc)

        for group in groups:
            evaluated += 1
            group_id = str(group.id)

            # Respect cooldown period
            if group.last_scaled_at:
                cooldown_expires = group.last_scaled_at + timedelta(
                    seconds=group.cooldown_seconds
                )
                if now < cooldown_expires:
                    remaining = (cooldown_expires - now).total_seconds()
                    logger.debug(
                        "Group %s (%s) is in cooldown (%.0fs remaining)",
                        group.name,
                        group_id,
                        remaining,
                    )
                    details.append({
                        "group_id": group_id,
                        "name": group.name,
                        "action": "cooldown",
                        "remaining_seconds": int(remaining),
                    })
                    continue

            # Fetch metrics and calculate desired count
            metrics = _get_group_metrics(group_id)
            group_dict = {
                "current_count": group.current_count,
                "min_instances": group.min_instances,
                "max_instances": group.max_instances,
                "scale_up_threshold": group.scale_up_threshold,
                "scale_down_threshold": group.scale_down_threshold,
            }

            desired = scaling_service.calculate_desired_count(group_dict, metrics)

            if desired != group.current_count:
                logger.info(
                    "Dispatching scale_group for %s (%s): "
                    "current=%d -> desired=%d (avg_cpu=%.1f)",
                    group.name,
                    group_id,
                    group.current_count,
                    desired,
                    metrics.get("avg_cpu", 0),
                )
                scale_group.delay(group_id, desired)
                scaled += 1
                details.append({
                    "group_id": group_id,
                    "name": group.name,
                    "action": "scaling",
                    "current_count": group.current_count,
                    "desired_count": desired,
                    "avg_cpu": metrics.get("avg_cpu"),
                })
            else:
                details.append({
                    "group_id": group_id,
                    "name": group.name,
                    "action": "no_change",
                    "current_count": group.current_count,
                    "avg_cpu": metrics.get("avg_cpu"),
                })

    logger.info(
        "check_scaling_triggers completed: evaluated=%d scaled=%d",
        evaluated,
        scaled,
    )

    return {
        "status": "completed",
        "evaluated": evaluated,
        "scaled": scaled,
        "details": details,
    }
