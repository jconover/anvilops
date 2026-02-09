"""
Scaling logic for Auto Scaling Group support.

Provides ``ScalingService`` which encapsulates the business rules for
calculating desired counts, creating new group members (by spawning
server build requests), and decommissioning excess members.
"""

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.scaling import ScalingGroup, ScalingGroupMember
from app.models.server import ServerRequest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Name generation helpers (mirrors app.api.v1.servers logic)
# ---------------------------------------------------------------------------

ENV_ABBREV = {"dev": "DEV", "staging": "STG", "production": "PROD"}
ROLE_ABBREV = {
    "base": "SRV",
    "web_server": "WEB",
    "db_server": "DB",
    "app_server": "APP",
    "dev_workstation": "DEV",
}


def _generate_server_name(environment: str, puppet_role: str) -> str:
    """Generate server name in ENV-ROLE-RANDOM format (e.g. PROD-WEB-a3f8)."""
    env = ENV_ABBREV.get(environment, "SRV")
    role = ROLE_ABBREV.get(puppet_role, "SRV")
    suffix = secrets.token_hex(2)
    return f"{env}-{role}-{suffix}"


class ScalingService:
    """Business logic for scaling group operations.

    All methods accept a synchronous ``Session`` (for Celery tasks) or
    perform self-contained DB operations.
    """

    # ------------------------------------------------------------------
    # Desired count calculation
    # ------------------------------------------------------------------

    def calculate_desired_count(
        self, group: dict[str, Any], metrics: dict[str, Any]
    ) -> int:
        """Determine desired instance count based on metrics and thresholds.

        The algorithm is intentionally simple for the demo:
        - If average CPU >= scale_up_threshold, add one instance (up to max).
        - If average CPU <= scale_down_threshold, remove one instance (down
          to min).
        - Otherwise, keep the current count.

        Args:
            group: Dict representation of a ``ScalingGroup`` row. Expected
                keys: ``current_count``, ``min_instances``, ``max_instances``,
                ``scale_up_threshold``, ``scale_down_threshold``.
            metrics: Dict with at least ``avg_cpu`` (float, 0-100).

        Returns:
            The new desired instance count.
        """
        current = group["current_count"]
        min_inst = group["min_instances"]
        max_inst = group["max_instances"]
        up_thresh = group["scale_up_threshold"]
        down_thresh = group["scale_down_threshold"]

        avg_cpu = metrics.get("avg_cpu", 0.0)

        if avg_cpu >= up_thresh and current < max_inst:
            desired = min(current + 1, max_inst)
            logger.info(
                "Scale-up triggered: avg_cpu=%.1f >= threshold=%d, "
                "desired %d -> %d",
                avg_cpu,
                up_thresh,
                current,
                desired,
            )
            return desired

        if avg_cpu <= down_thresh and current > min_inst:
            desired = max(current - 1, min_inst)
            logger.info(
                "Scale-down triggered: avg_cpu=%.1f <= threshold=%d, "
                "desired %d -> %d",
                avg_cpu,
                down_thresh,
                current,
                desired,
            )
            return desired

        return current

    # ------------------------------------------------------------------
    # Member lifecycle
    # ------------------------------------------------------------------

    def create_group_member(
        self, session: Session, group_id: str, member_index: int
    ) -> str:
        """Create a new server request from the group template and register
        it as a scaling group member.

        The new ``ServerRequest`` is created with status ``pending`` and
        will be picked up by the standard Celery build orchestrator.

        Args:
            session: Active synchronous DB session.
            group_id: UUID string of the ``ScalingGroup``.
            member_index: Ordinal index for this member within the group.

        Returns:
            The UUID string of the newly created ``ServerRequest``.
        """
        group = session.get(ScalingGroup, group_id)
        if group is None:
            raise ValueError(f"ScalingGroup not found: {group_id}")

        server_name = _generate_server_name(group.environment, group.puppet_role)

        server_request = ServerRequest(
            id=uuid.uuid4(),
            server_name=server_name,
            environment=group.environment,
            os_type=group.os_type,
            instance_size=group.instance_size,
            region=group.region,
            vpc_id=group.vpc_id,
            subnet_id=group.subnet_id,
            security_profile=group.security_profile,
            puppet_role=group.puppet_role,
            domain_join=False,
            software_packages=[],
            additional_storage=[],
            tags={
                "scaling_group_id": str(group.id),
                "scaling_group_name": group.name,
                "member_index": str(member_index),
            },
            status="pending",
        )
        session.add(server_request)
        session.flush()

        member = ScalingGroupMember(
            id=uuid.uuid4(),
            scaling_group_id=uuid.UUID(group_id),
            server_request_id=server_request.id,
            member_index=member_index,
            status="active",
        )
        session.add(member)
        session.flush()

        # Update current count on the group
        group.current_count = (
            session.query(ScalingGroupMember)
            .filter(
                ScalingGroupMember.scaling_group_id == uuid.UUID(group_id),
                ScalingGroupMember.status == "active",
            )
            .count()
        )

        logger.info(
            "Created scaling group member index=%d for group %s: "
            "server_request=%s (%s)",
            member_index,
            group.name,
            server_request.id,
            server_name,
        )

        # Dispatch the standard build task for the new server
        try:
            from app.tasks.orchestrator import run_server_build

            run_server_build.delay(str(server_request.id))
        except ImportError:
            logger.warning(
                "Celery build task not available; skipping dispatch for %s",
                server_request.id,
            )

        return str(server_request.id)

    def remove_group_member(
        self, session: Session, group_id: str, member_id: str
    ) -> None:
        """Decommission a group member.

        Marks the ``ScalingGroupMember`` as ``terminating``, kicks off the
        decommission workflow for the associated server, and updates the
        group's ``current_count``.

        Args:
            session: Active synchronous DB session.
            group_id: UUID string of the ``ScalingGroup``.
            member_id: UUID string of the ``ScalingGroupMember`` to remove.
        """
        member = session.get(ScalingGroupMember, member_id)
        if member is None:
            raise ValueError(f"ScalingGroupMember not found: {member_id}")

        if str(member.scaling_group_id) != group_id:
            raise ValueError(
                f"Member {member_id} does not belong to group {group_id}"
            )

        member.status = "terminating"
        member.updated_at = datetime.now(timezone.utc)
        session.flush()

        # Trigger decommission of the underlying server, if it exists
        if member.server_request_id:
            server = session.get(ServerRequest, str(member.server_request_id))
            if server and server.status in ("ready", "failed"):
                server.status = "decommissioning"
                server.status_message = (
                    f"Decommissioned by scaling group scale-down "
                    f"(group={group_id})"
                )
                server.updated_at = datetime.now(timezone.utc)
                session.flush()

                try:
                    from app.tasks.decommission import run_server_decommission

                    run_server_decommission.delay(str(server.id))
                except ImportError:
                    logger.warning(
                        "Celery decommission task not available; "
                        "skipping dispatch for %s",
                        server.id,
                    )

        # Update current count
        group = session.get(ScalingGroup, group_id)
        if group is not None:
            group.current_count = (
                session.query(ScalingGroupMember)
                .filter(
                    ScalingGroupMember.scaling_group_id == uuid.UUID(group_id),
                    ScalingGroupMember.status == "active",
                )
                .count()
            )
            group.updated_at = datetime.now(timezone.utc)

        logger.info(
            "Marked scaling group member %s (index=%d) for termination "
            "in group %s",
            member_id,
            member.member_index,
            group_id,
        )

    # ------------------------------------------------------------------
    # Helpers for scaling tasks
    # ------------------------------------------------------------------

    def get_next_member_index(self, session: Session, group_id: str) -> int:
        """Return the next available member index for a group.

        Uses ``max(member_index) + 1`` to ensure monotonically increasing
        indices even after members are removed.
        """
        from sqlalchemy import func

        result = (
            session.query(func.max(ScalingGroupMember.member_index))
            .filter(
                ScalingGroupMember.scaling_group_id == uuid.UUID(group_id),
            )
            .scalar()
        )
        return (result or 0) + 1

    def get_removable_members(
        self, session: Session, group_id: str, count: int
    ) -> list[ScalingGroupMember]:
        """Return the *count* newest active members eligible for removal.

        Members are ordered by ``created_at DESC`` so the most recently
        created servers are removed first (newest-first strategy).
        """
        return (
            session.query(ScalingGroupMember)
            .filter(
                ScalingGroupMember.scaling_group_id == uuid.UUID(group_id),
                ScalingGroupMember.status == "active",
            )
            .order_by(ScalingGroupMember.created_at.desc())
            .limit(count)
            .all()
        )
