"""
AWX (Ansible) Celery tasks for AnvilOps.

Provides tasks that drive the AWX configuration pipeline after Terraform
has provisioned an EC2 instance.  Each task follows the same conventions
as the Terraform tasks: progress is persisted to BuildStep records,
errors are captured, and results are returned as plain dicts for
JSON serialisation.

Tasks:
  - awx_configure   -- Run the Day-1 configuration pipeline via AWX.
  - awx_decommission -- Remove a host from AWX during server teardown.
"""

import json
import logging
from datetime import datetime, timezone

from app.worker.celery_app import celery_app
from app.services.db import (
    get_sync_db,
    get_server_request,
    update_build_step,
)
from app.core.config import settings

try:
    from app.services.awx import AWXServiceSync
    from app.services.awx_exceptions import AWXError
except ImportError:
    AWXServiceSync = None  # type: ignore[assignment,misc]
    AWXError = Exception  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


def _get_awx_service() -> "AWXServiceSync":
    """Construct a synchronous AWX client using application settings."""
    if AWXServiceSync is None:
        raise RuntimeError(
            "AWXServiceSync is not available -- ensure app.services.awx is installed"
        )
    return AWXServiceSync(
        base_url=settings.AWX_BASE_URL,
        username=settings.AWX_USERNAME,
        password=settings.AWX_PASSWORD,
        timeout=30.0,
    )


def _summarise_jobs(jobs: list[dict]) -> str:
    """Build a human-readable summary of AWX job results for the build log."""
    lines: list[str] = []
    for job in jobs:
        status = job.get("status", "unknown")
        template = job.get("template", "unknown")
        job_id = job.get("job_id", "n/a")
        line = f"  [{status.upper()}] {template} (job {job_id})"
        error = job.get("error")
        if error:
            line += f" -- {error}"
        lines.append(line)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# awx_configure
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="tasks.awx_configure")
def awx_configure(
    self, server_request_id: str, build_step_id: str | None = None
) -> dict:
    """Run the Day-1 AWX configuration pipeline for a provisioned server.

    Called by the orchestrator after ``terraform_apply`` succeeds.  The task:

    1. Loads the server request from the database (which now includes
       ``private_ip`` / ``public_ip`` populated by Terraform).
    2. Marks the build step as *in_progress*.
    3. Delegates to ``AWXServiceSync.run_configuration_pipeline`` which
       handles inventory setup, host registration, and sequential job
       template execution.
    4. Records success or failure on the build step.

    Returns:
        A dict with ``exit_code`` (0 = success, 1 = failure), ``output``
        (human-readable log), and ``jobs`` (list of per-template results).
    """
    logger.info("awx_configure starting for %s", server_request_id)

    # Mark build step as in-progress
    if build_step_id:
        with get_sync_db() as session:
            update_build_step(
                session,
                build_step_id,
                status="in_progress",
                started_at=datetime.now(timezone.utc),
            )

    # Load latest server request data (should now include IPs from Terraform)
    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    awx = _get_awx_service()
    try:
        pipeline_result = awx.run_configuration_pipeline(server_data)

        jobs = pipeline_result.get("jobs", [])
        host_id = pipeline_result.get("host_id")
        success = pipeline_result.get("success", False)

        job_summary = _summarise_jobs(jobs)
        if success:
            output_log = (
                f"AWX configuration pipeline succeeded for {server_data['server_name']}\n"
                f"Host ID: {host_id}\n"
                f"Jobs:\n{job_summary}"
            )
        else:
            output_log = (
                f"AWX configuration pipeline FAILED for {server_data['server_name']}\n"
                f"Host ID: {host_id}\n"
                f"Jobs:\n{job_summary}"
            )

        # Update build step
        if build_step_id:
            with get_sync_db() as session:
                update_build_step(
                    session,
                    build_step_id,
                    status="completed" if success else "failed",
                    output_log=output_log[-10000:],
                    completed_at=datetime.now(timezone.utc),
                )

        exit_code = 0 if success else 1
        if not success:
            logger.error(
                "AWX configuration failed for %s: %s",
                server_request_id,
                output_log[:500],
            )
        else:
            logger.info(
                "AWX configuration completed for %s (host_id=%s, %d jobs)",
                server_request_id,
                host_id,
                len(jobs),
            )

        return {
            "exit_code": exit_code,
            "output": output_log,
            "jobs": jobs,
            "host_id": host_id,
        }

    except Exception as exc:
        logger.exception("awx_configure error for %s: %s", server_request_id, exc)
        error_message = str(exc)

        if build_step_id:
            with get_sync_db() as session:
                update_build_step(
                    session,
                    build_step_id,
                    status="failed",
                    error_message=error_message[:1000],
                    completed_at=datetime.now(timezone.utc),
                )

        return {
            "exit_code": 1,
            "output": f"AWX configuration error: {error_message}",
            "jobs": [],
            "host_id": None,
        }

    finally:
        try:
            awx.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# awx_decommission
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="tasks.awx_decommission")
def awx_decommission(self, server_request_id: str) -> dict:
    """Remove a server's host entry from AWX during decommission or rollback.

    Looks up the server request to find the AWX host ID (stored as
    ``awx_host_id`` on the ServerRequest model).  If present, the host
    is deleted from AWX inventory.

    This task is intentionally best-effort: failures are logged but do
    not raise exceptions so that the broader decommission workflow can
    continue.

    Returns:
        A dict with ``exit_code`` and ``output``.
    """
    logger.info("awx_decommission starting for %s", server_request_id)

    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    awx_host_id = server_data.get("awx_host_id")
    server_name = server_data.get("server_name", server_request_id)

    if not awx_host_id:
        msg = (
            f"No AWX host ID recorded for {server_name} "
            f"(request {server_request_id}), skipping AWX cleanup"
        )
        logger.info(msg)
        return {"exit_code": 0, "output": msg}

    awx = _get_awx_service()
    try:
        awx.remove_host(awx_host_id)
        msg = f"Removed AWX host {awx_host_id} ({server_name}) from inventory"
        logger.info(msg)
        return {"exit_code": 0, "output": msg}

    except Exception as exc:
        error_msg = (
            f"Failed to remove AWX host {awx_host_id} ({server_name}): {exc}"
        )
        logger.exception(error_msg)
        return {"exit_code": 1, "output": error_msg}

    finally:
        try:
            awx.close()
        except Exception:
            pass
