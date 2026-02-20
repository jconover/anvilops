"""Celery tasks for the scheduled builds system.

Two tasks collaborate to drive scheduled server provisioning:

1. ``process_scheduled_builds`` -- A periodic task (meant to run via
   Celery Beat every 60 seconds) that scans for active schedules whose
   ``next_run_at`` has arrived, creates execution records, dispatches
   individual build tasks, and advances the schedule state.

2. ``execute_scheduled_build`` -- Executes a single scheduled build by
   creating a ServerRequest from the schedule's ``server_config`` JSON
   and dispatching the standard ``run_server_build`` orchestration task.
"""

import logging
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from app.models.schedule import BuildSchedule, ScheduleExecution
from app.models.server import ServerRequest
from app.services.cron_parser import get_next_run
from app.services.db import get_sync_db
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name generation (duplicated from servers.py to avoid import tangles
# with the async API layer in sync Celery workers)
# ---------------------------------------------------------------------------

_ENV_ABBREV = {"dev": "DEV", "staging": "STG", "production": "PROD"}
_ROLE_ABBREV = {
    "base": "SRV",
    "web_server": "WEB",
    "db_server": "DB",
    "app_server": "APP",
    "dev_workstation": "DEV",
}


def _generate_server_name(environment: str, puppet_role: str) -> str:
    env = _ENV_ABBREV.get(environment, "SRV")
    role = _ROLE_ABBREV.get(puppet_role, "SRV")
    suffix = secrets.token_hex(2)
    return f"{env}-{role}-{suffix}"


# ---------------------------------------------------------------------------
# Periodic beat task
# ---------------------------------------------------------------------------


@celery_app.task(name="tasks.process_scheduled_builds")
def process_scheduled_builds() -> dict:
    """Periodic task to check for and dispatch due scheduled builds.

    Intended to be called by Celery Beat every 60 seconds.  For each
    active schedule whose ``next_run_at`` is at or before the current
    time:

    1. Create a ``ScheduleExecution`` record in ``pending`` status.
    2. Dispatch ``execute_scheduled_build`` as a separate Celery task.
    3. Update the schedule's ``run_count``, ``last_run_at``, and
       ``next_run_at``.
    4. If the schedule has reached ``max_runs`` or is a one-time
       schedule, transition it to ``completed``.
    """
    now = datetime.now(timezone.utc)
    dispatched = 0
    completed_schedules = 0
    errors = 0
    due_count = 0

    logger.info("Processing scheduled builds at %s", now.isoformat())

    with get_sync_db() as session:
        # Find all active schedules that are due
        due_schedules = (
            session.query(BuildSchedule)
            .filter(
                BuildSchedule.status == "active",
                BuildSchedule.next_run_at.isnot(None),
                BuildSchedule.next_run_at <= now,
            )
            .all()
        )

        due_count = len(due_schedules)
        logger.info("Found %d due schedule(s)", due_count)

        for schedule in due_schedules:
            try:
                # Create an execution record
                execution = ScheduleExecution(
                    id=uuid4(),
                    schedule_id=schedule.id,
                    status="pending",
                    scheduled_for=schedule.next_run_at,
                )
                session.add(execution)

                # Update schedule counters
                schedule.run_count += 1
                schedule.last_run_at = now
                schedule.updated_at = now

                # Compute next_run_at
                if schedule.schedule_type == "one_time":
                    schedule.next_run_at = None
                    schedule.status = "completed"
                    completed_schedules += 1
                elif schedule.max_runs is not None and schedule.run_count >= schedule.max_runs:
                    schedule.next_run_at = None
                    schedule.status = "completed"
                    completed_schedules += 1
                else:
                    # Recurring -- calculate next run time
                    try:
                        schedule.next_run_at = get_next_run(
                            schedule.cron_expression,
                            after=now,
                            timezone=schedule.timezone or "UTC",
                        )
                    except (ValueError, KeyError) as exc:
                        logger.error(
                            "Failed to compute next_run_at for schedule %s: %s",
                            schedule.id,
                            exc,
                        )
                        schedule.next_run_at = None
                        schedule.status = "completed"
                        completed_schedules += 1

                # Flush so the execution record gets an ID we can pass to the task
                session.flush()

                # Dispatch the individual build task
                execute_scheduled_build.delay(
                    str(schedule.id), str(execution.id)
                )
                dispatched += 1

                logger.info(
                    "Dispatched scheduled build: schedule=%s execution=%s next_run=%s",
                    schedule.id,
                    execution.id,
                    schedule.next_run_at,
                )

            except Exception:
                logger.exception(
                    "Error processing schedule %s", schedule.id
                )
                errors += 1

    result = {
        "processed_at": now.isoformat(),
        "due_count": due_count,
        "dispatched": dispatched,
        "completed_schedules": completed_schedules,
        "errors": errors,
    }
    logger.info("Scheduled builds processing complete: %s", result)
    return result


# ---------------------------------------------------------------------------
# Individual build execution task
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="tasks.execute_scheduled_build",
    max_retries=2,
    default_retry_delay=30,
)
def execute_scheduled_build(self, schedule_id: str, execution_id: str) -> dict:
    """Execute a single scheduled build.

    1. Load the schedule and execution from the database.
    2. Create a ``ServerRequest`` from the schedule's ``server_config``.
    3. Dispatch the standard ``run_server_build`` orchestration task.
    4. Update the execution record with the outcome.

    On transient failures the task retries up to 2 times with a
    30-second delay.
    """
    logger.info(
        "Executing scheduled build: schedule=%s execution=%s",
        schedule_id,
        execution_id,
    )

    now = datetime.now(timezone.utc)

    try:
        with get_sync_db() as session:
            # Load schedule and execution
            schedule = session.get(BuildSchedule, schedule_id)
            if schedule is None:
                raise ValueError(f"BuildSchedule not found: {schedule_id}")

            execution = session.get(ScheduleExecution, execution_id)
            if execution is None:
                raise ValueError(f"ScheduleExecution not found: {execution_id}")

            # Mark execution as running
            execution.status = "running"
            execution.started_at = now
            execution.updated_at = now
            session.flush()

            # Build the ServerRequest from the stored config
            config = schedule.server_config
            server_name = config.get("server_name") or _generate_server_name(
                config.get("environment", "dev"),
                config.get("puppet_role", "base"),
            )

            # Prepare additional_storage as a list of dicts
            additional_storage = config.get("additional_storage", [])
            if additional_storage and isinstance(additional_storage[0], dict):
                storage_data = additional_storage
            else:
                storage_data = []

            server = ServerRequest(
                id=uuid4(),
                server_name=server_name,
                environment=config.get("environment", "dev"),
                os_type=config.get("os_type", "amazon_linux_2023"),
                instance_size=config.get("instance_size", "small"),
                region=config.get("region", "us-east-1"),
                vpc_id=config.get("vpc_id", ""),
                subnet_id=config.get("subnet_id", ""),
                security_profile=config.get("security_profile", "internal_only"),
                domain_join=config.get("domain_join", False),
                software_packages=config.get("software_packages", []),
                puppet_role=config.get("puppet_role", "base"),
                additional_storage=storage_data,
                tags=config.get("tags", {}),
                template_id=config.get("template_id"),
                status="pending",
            )
            session.add(server)
            session.flush()

            server_request_id = str(server.id)

            # Link execution to the server request
            execution.server_request_id = server.id
            execution.updated_at = datetime.now(timezone.utc)
            session.flush()

        logger.info(
            "Created server request %s (%s) from schedule %s",
            server.server_name,
            server_request_id,
            schedule_id,
        )

        # Dispatch the standard build orchestration task
        try:
            from app.tasks.orchestrator import run_server_build
            run_server_build.delay(server_request_id)
        except ImportError:
            logger.warning(
                "run_server_build task not available, marking execution as completed"
            )

        # Mark execution as completed (the actual build runs asynchronously)
        with get_sync_db() as session:
            execution = session.get(ScheduleExecution, execution_id)
            if execution is not None:
                execution.status = "completed"
                execution.completed_at = datetime.now(timezone.utc)
                execution.updated_at = datetime.now(timezone.utc)

        logger.info(
            "Scheduled build execution completed: schedule=%s execution=%s server=%s",
            schedule_id,
            execution_id,
            server_request_id,
        )

        return {
            "status": "completed",
            "schedule_id": schedule_id,
            "execution_id": execution_id,
            "server_request_id": server_request_id,
        }

    except ValueError as exc:
        # Non-retryable errors (missing records)
        logger.error("Scheduled build execution failed: %s", exc)
        _mark_execution_failed(execution_id, str(exc))
        return {
            "status": "failed",
            "schedule_id": schedule_id,
            "execution_id": execution_id,
            "error": str(exc),
        }

    except Exception as exc:
        logger.exception(
            "Scheduled build execution error: schedule=%s execution=%s",
            schedule_id,
            execution_id,
        )
        _mark_execution_failed(execution_id, str(exc)[:1000])

        # Retry on transient failures
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for scheduled build: schedule=%s execution=%s",
                schedule_id,
                execution_id,
            )
            return {
                "status": "failed",
                "schedule_id": schedule_id,
                "execution_id": execution_id,
                "error": f"Max retries exceeded: {str(exc)[:500]}",
            }


def _mark_execution_failed(execution_id: str, error_message: str) -> None:
    """Helper to mark a ScheduleExecution as failed."""
    try:
        with get_sync_db() as session:
            execution = session.get(ScheduleExecution, execution_id)
            if execution is not None:
                execution.status = "failed"
                execution.error_message = error_message
                execution.completed_at = datetime.now(timezone.utc)
                execution.updated_at = datetime.now(timezone.utc)
    except Exception:
        logger.exception(
            "Failed to mark execution %s as failed", execution_id
        )
