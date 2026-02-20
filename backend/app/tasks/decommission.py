"""
Decommission orchestration task for AnvilOps.

Coordinates the full server teardown workflow (reverse of provisioning):
  1. Mark server as "decommissioning"
  2. Create decommission build steps
  3. Puppet node purge (remove from PE)
  4. AWX decommission playbook (cleanup agents, leave domain, etc.)
  5. Terraform destroy (terminate EC2, release EIP, delete SG, etc.)
  6. DNS cleanup (remove DNS records)
  7. Mark as "decommissioned"

Each step is best-effort -- if Puppet purge fails, we still proceed with
AWX decom and Terraform destroy.  Only Terraform destroy failure is
considered a hard failure that leaves the server in "failed" state.

The pipeline mirrors the structure of the build orchestrator
(``app.tasks.orchestrator.run_server_build``) for consistency: each step
updates its corresponding BuildStep record, and the overall status is
managed on the ServerRequest.
"""

import logging
from datetime import datetime, timezone

from app.services.db import (
    create_build_steps,
    get_server_request,
    get_sync_db,
    update_build_step,
    update_server_status,
)
from app.worker.celery_app import celery_app

try:
    from app.tasks.puppet import puppet_decommission
except ImportError:
    puppet_decommission = None  # type: ignore[assignment]

try:
    from app.tasks.awx import awx_decommission
except ImportError:
    awx_decommission = None  # type: ignore[assignment]

try:
    from app.tasks.terraform import terraform_destroy
except ImportError:
    terraform_destroy = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# The decommission pipeline steps, executed in order.
# This is the reverse of provisioning: Puppet -> AWX -> Terraform -> DNS.
DECOM_STEPS = [
    "puppet_purge",
    "awx_decommission",
    "terraform_destroy",
    "dns_cleanup",
]

# Statuses from which a server can be decommissioned.
DECOMMISSIONABLE_STATUSES = frozenset({"ready", "failed"})


def _run_puppet_purge(server_request_id: str, step_id: str) -> dict:
    """Execute the Puppet node purge step.

    Calls ``puppet_decommission`` to remove the node from Puppet
    Enterprise (PuppetDB deactivation, classifier unpin, cert revoke +
    delete).

    This step is best-effort: failures are captured and logged but do
    not stop the decommission pipeline.

    Args:
        server_request_id: UUID of the server request being decommissioned.
        step_id: UUID of the corresponding BuildStep record.

    Returns:
        Dict with ``exit_code`` and ``output``.
    """
    logger.info("Decommission step: puppet_purge for %s", server_request_id)

    with get_sync_db() as session:
        update_build_step(
            session,
            step_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )

    if puppet_decommission is None:
        msg = (
            "puppet_decommission task not available; "
            "skipping Puppet purge for %s" % server_request_id
        )
        logger.warning(msg)
        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="completed",
                output_log=msg,
                completed_at=datetime.now(timezone.utc),
            )
        return {"exit_code": 0, "output": msg}

    try:
        result = puppet_decommission(server_request_id)
        exit_code = result.get("exit_code", 1)
        output = result.get("output", "")

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="completed" if exit_code == 0 else "failed",
                output_log=output[-10000:],
                completed_at=datetime.now(timezone.utc),
            )

        if exit_code != 0:
            logger.warning(
                "Puppet purge failed for %s (best-effort, continuing): %s",
                server_request_id,
                output[:500],
            )
        else:
            logger.info("Puppet purge succeeded for %s", server_request_id)

        return result

    except Exception as exc:
        error_msg = f"Puppet purge error for {server_request_id}: {exc}"
        logger.exception(error_msg)

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="failed",
                error_message=str(exc)[:1000],
                completed_at=datetime.now(timezone.utc),
            )

        return {"exit_code": 1, "output": error_msg}


def _run_awx_decommission(server_request_id: str, step_id: str) -> dict:
    """Execute the AWX decommission step.

    Calls ``awx_decommission`` to remove the host from AWX inventory.
    In a full implementation this would also run a decommission playbook
    (leave domain, uninstall agents, etc.) before removing the host.

    This step is best-effort: failures are captured and logged but do
    not stop the decommission pipeline.

    Args:
        server_request_id: UUID of the server request being decommissioned.
        step_id: UUID of the corresponding BuildStep record.

    Returns:
        Dict with ``exit_code`` and ``output``.
    """
    logger.info(
        "Decommission step: awx_decommission for %s", server_request_id
    )

    with get_sync_db() as session:
        update_build_step(
            session,
            step_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )

    if awx_decommission is None:
        msg = (
            "awx_decommission task not available; "
            "skipping AWX cleanup for %s" % server_request_id
        )
        logger.warning(msg)
        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="completed",
                output_log=msg,
                completed_at=datetime.now(timezone.utc),
            )
        return {"exit_code": 0, "output": msg}

    try:
        result = awx_decommission(server_request_id)
        exit_code = result.get("exit_code", 1)
        output = result.get("output", "")

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="completed" if exit_code == 0 else "failed",
                output_log=output[-10000:],
                completed_at=datetime.now(timezone.utc),
            )

        if exit_code != 0:
            logger.warning(
                "AWX decommission failed for %s (best-effort, continuing): %s",
                server_request_id,
                output[:500],
            )
        else:
            logger.info(
                "AWX decommission succeeded for %s", server_request_id
            )

        return result

    except Exception as exc:
        error_msg = f"AWX decommission error for {server_request_id}: {exc}"
        logger.exception(error_msg)

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="failed",
                error_message=str(exc)[:1000],
                completed_at=datetime.now(timezone.utc),
            )

        return {"exit_code": 1, "output": error_msg}


def _run_terraform_destroy(server_request_id: str, step_id: str) -> dict:
    """Execute the Terraform destroy step.

    Calls ``terraform_destroy`` to terminate the EC2 instance and
    tear down all associated infrastructure (security groups, EBS
    volumes, IAM roles, etc.).

    Unlike Puppet purge and AWX decommission, Terraform destroy failure
    IS a hard failure -- the infrastructure is still running and billed.

    Args:
        server_request_id: UUID of the server request being decommissioned.
        step_id: UUID of the corresponding BuildStep record.

    Returns:
        Dict with ``exit_code`` and ``output``.
    """
    logger.info(
        "Decommission step: terraform_destroy for %s", server_request_id
    )

    with get_sync_db() as session:
        update_build_step(
            session,
            step_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )

    if terraform_destroy is None:
        error_msg = (
            "terraform_destroy task not available; "
            "cannot destroy infrastructure for %s" % server_request_id
        )
        logger.error(error_msg)
        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="failed",
                error_message=error_msg,
                completed_at=datetime.now(timezone.utc),
            )
        return {"exit_code": 1, "output": error_msg}

    try:
        result = terraform_destroy(server_request_id)
        exit_code = result.get("exit_code", 1)
        output = result.get("output", "")

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="completed" if exit_code == 0 else "failed",
                output_log=output[-10000:],
                completed_at=datetime.now(timezone.utc),
            )

        if exit_code != 0:
            logger.error(
                "Terraform destroy FAILED for %s: %s",
                server_request_id,
                output[:500],
            )
        else:
            logger.info(
                "Terraform destroy succeeded for %s", server_request_id
            )

        return result

    except Exception as exc:
        error_msg = (
            f"Terraform destroy error for {server_request_id}: {exc}"
        )
        logger.exception(error_msg)

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="failed",
                error_message=str(exc)[:1000],
                completed_at=datetime.now(timezone.utc),
            )

        return {"exit_code": 1, "output": error_msg}


def _run_dns_cleanup(server_request_id: str, step_id: str) -> dict:
    """Execute the DNS cleanup step.

    Uses ``DNSCleanupService`` to remove DNS records for the server.
    Currently a stub that logs what would be cleaned up.

    This step is best-effort: failures are captured and logged but do
    not stop the decommission pipeline.

    Args:
        server_request_id: UUID of the server request being decommissioned.
        step_id: UUID of the corresponding BuildStep record.

    Returns:
        Dict with ``exit_code`` and ``output``.
    """
    logger.info("Decommission step: dns_cleanup for %s", server_request_id)

    with get_sync_db() as session:
        update_build_step(
            session,
            step_id,
            status="in_progress",
            started_at=datetime.now(timezone.utc),
        )

    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    server_name = server_data.get("server_name", server_request_id)
    dns_name = server_data.get("dns_name")
    private_ip = server_data.get("private_ip")
    public_ip = server_data.get("public_ip")

    try:
        from app.services.dns import DNSCleanupService

        dns_service = DNSCleanupService()
        result = dns_service.cleanup_records(
            server_name=server_name,
            dns_name=dns_name,
            private_ip=private_ip,
            public_ip=public_ip,
        )

        exit_code = result.get("exit_code", 1)
        output = result.get("output", "")

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="completed" if exit_code == 0 else "failed",
                output_log=output[-10000:],
                completed_at=datetime.now(timezone.utc),
            )

        if exit_code != 0:
            logger.warning(
                "DNS cleanup failed for %s (best-effort, continuing): %s",
                server_request_id,
                output[:500],
            )
        else:
            logger.info("DNS cleanup succeeded for %s", server_request_id)

        return result

    except Exception as exc:
        error_msg = f"DNS cleanup error for {server_request_id}: {exc}"
        logger.exception(error_msg)

        with get_sync_db() as session:
            update_build_step(
                session,
                step_id,
                status="failed",
                error_message=str(exc)[:1000],
                completed_at=datetime.now(timezone.utc),
            )

        return {"exit_code": 1, "output": error_msg}


def _clear_server_metadata(server_request_id: str) -> None:
    """Clear infrastructure metadata from the server request.

    After a successful decommission the AWS instance, IPs, DNS name,
    AWX host, and Puppet enrollment data are no longer valid. This
    helper nulls out those fields so the decommissioned record does
    not reference stale infrastructure.

    Args:
        server_request_id: UUID of the server request to clear.
    """
    logger.info(
        "Clearing infrastructure metadata for %s", server_request_id
    )

    with get_sync_db() as session:
        from app.models.server import ServerRequest

        sr = session.get(ServerRequest, server_request_id)
        if sr is None:
            logger.error(
                "ServerRequest not found for metadata cleanup: %s",
                server_request_id,
            )
            return

        sr.aws_instance_id = None
        sr.private_ip = None
        sr.public_ip = None
        sr.dns_name = None
        sr.awx_host_id = None
        sr.awx_inventory_id = None
        sr.awx_job_ids = None
        sr.puppet_certname = None
        sr.puppet_node_group_id = None
        sr.puppet_last_report_status = None
        sr.puppet_enrolled_at = None
        sr.updated_at = datetime.now(timezone.utc)

    logger.info("Cleared infrastructure metadata for %s", server_request_id)


# ---------------------------------------------------------------------------
# Step dispatch map
# ---------------------------------------------------------------------------

_STEP_DISPATCH = {
    "puppet_purge": _run_puppet_purge,
    "awx_decommission": _run_awx_decommission,
    "terraform_destroy": _run_terraform_destroy,
    "dns_cleanup": _run_dns_cleanup,
}


# ---------------------------------------------------------------------------
# Main decommission task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="tasks.run_server_decommission", max_retries=0)
def run_server_decommission(self, server_request_id: str) -> dict:
    """Main entry point for decommissioning a server.

    Executes the full teardown pipeline:
      Puppet purge -> AWX decommission -> Terraform destroy -> DNS cleanup.

    Error handling follows a best-effort strategy for soft steps and a
    hard-failure strategy for Terraform destroy:

    - **Puppet purge** and **AWX decommission** are best-effort.  If they
      fail the pipeline logs the error and continues.  The infrastructure
      must still be destroyed regardless.

    - **Terraform destroy** is a hard requirement.  If it fails the server
      is marked as ``failed`` with a descriptive status message.  The
      infrastructure is still running and manual intervention is needed.

    - **DNS cleanup** is best-effort (and currently a stub).

    On full success the server is marked as ``decommissioned`` and all
    infrastructure metadata (instance IDs, IPs, DNS names, AWX/Puppet
    references) is cleared from the database record.

    Args:
        server_request_id: UUID string of the server request to
            decommission.

    Returns:
        Dict with ``status``, ``server_request_id``, per-step results,
        and any error information.
    """
    logger.info(
        "Starting server decommission for request %s", server_request_id
    )

    # ------------------------------------------------------------------
    # 1. Validate server exists and is in a decommissionable state
    # ------------------------------------------------------------------
    with get_sync_db() as session:
        try:
            server_data = get_server_request(session, server_request_id)
        except ValueError:
            logger.error(
                "ServerRequest not found: %s", server_request_id
            )
            return {
                "status": "failed",
                "server_request_id": server_request_id,
                "error": f"ServerRequest not found: {server_request_id}",
            }

    current_status = server_data.get("status", "unknown")

    # The API endpoint should have already set the status to
    # "decommissioning", but verify it here as a safety check.  Also
    # allow "ready" and "failed" in case the task is triggered directly.
    if current_status not in ("decommissioning", *DECOMMISSIONABLE_STATUSES):
        msg = (
            f"Server {server_request_id} is in status '{current_status}' "
            f"which is not decommissionable"
        )
        logger.error(msg)
        return {
            "status": "failed",
            "server_request_id": server_request_id,
            "error": msg,
        }

    server_name = server_data.get("server_name", server_request_id)

    # ------------------------------------------------------------------
    # 2. Mark as "decommissioning" and create build step records
    # ------------------------------------------------------------------
    with get_sync_db() as session:
        update_server_status(
            session,
            server_request_id,
            status="decommissioning",
            status_message="Decommission workflow started",
        )
        step_records = create_build_steps(
            session, server_request_id, DECOM_STEPS
        )
        step_ids = {rec["step_name"]: rec["id"] for rec in step_records}

    # Track per-step results for the return value.
    step_results: dict[str, dict] = {}
    terraform_failed = False

    # ------------------------------------------------------------------
    # 3. Execute each decommission step in sequence
    # ------------------------------------------------------------------
    for step_name in DECOM_STEPS:
        step_fn = _STEP_DISPATCH[step_name]
        step_id = step_ids[step_name]

        logger.info(
            "Running decommission step '%s' for %s (%s)",
            step_name,
            server_name,
            server_request_id,
        )

        result = step_fn(server_request_id, step_id)
        step_results[step_name] = result

        exit_code = result.get("exit_code", 1)

        # Terraform destroy failure is a hard stop.
        if step_name == "terraform_destroy" and exit_code != 0:
            terraform_failed = True
            logger.error(
                "Terraform destroy failed for %s -- "
                "infrastructure may still be running",
                server_request_id,
            )
            # Skip remaining steps (dns_cleanup) since the infra is
            # still alive and DNS records should remain.
            for remaining_step in DECOM_STEPS[DECOM_STEPS.index(step_name) + 1:]:
                remaining_id = step_ids[remaining_step]
                with get_sync_db() as session:
                    update_build_step(
                        session,
                        remaining_id,
                        status="cancelled",
                        output_log=(
                            "Skipped: Terraform destroy failed; "
                            "infrastructure still running"
                        ),
                        completed_at=datetime.now(timezone.utc),
                    )
                step_results[remaining_step] = {
                    "exit_code": -1,
                    "output": "Skipped due to Terraform destroy failure",
                }
            break

    # ------------------------------------------------------------------
    # 4. Determine final status
    # ------------------------------------------------------------------
    if terraform_failed:
        # Terraform destroy failed -- mark as failed so an operator can
        # investigate and re-run or manually clean up.
        error_msg = (
            "Decommission failed: Terraform destroy did not succeed. "
            "Infrastructure may still be running and incurring charges. "
            f"Details: {step_results.get('terraform_destroy', {}).get('output', '')[:300]}"
        )
        with get_sync_db() as session:
            update_server_status(
                session,
                server_request_id,
                status="failed",
                status_message=error_msg[:500],
            )

        logger.error(
            "Decommission failed for %s (%s): Terraform destroy error",
            server_name,
            server_request_id,
        )

        return {
            "status": "failed",
            "server_request_id": server_request_id,
            "server_name": server_name,
            "error": error_msg,
            "steps": step_results,
        }

    # ------------------------------------------------------------------
    # 5. Full success -- mark as decommissioned and clear metadata
    # ------------------------------------------------------------------
    _clear_server_metadata(server_request_id)

    with get_sync_db() as session:
        update_server_status(
            session,
            server_request_id,
            status="decommissioned",
            status_message="Server fully decommissioned",
        )

    logger.info(
        "Server decommission completed for %s (%s)",
        server_name,
        server_request_id,
    )

    return {
        "status": "decommissioned",
        "server_request_id": server_request_id,
        "server_name": server_name,
        "steps": step_results,
    }
