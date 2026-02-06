"""
Main build orchestration task for AnvilOps.

Coordinates the full server provisioning workflow:
  1. Load the server request from the database
  2. Create build step records for tracking
  3. Run terraform plan and apply
  4. On success, record AWS instance details
  5. On failure, trigger rollback via terraform destroy
"""

import logging
from datetime import datetime, timezone

from app.worker.celery_app import celery_app
from app.services.db import get_sync_db, update_server_status, create_build_steps
from app.tasks.terraform import terraform_plan, terraform_apply, terraform_destroy

logger = logging.getLogger(__name__)

PHASE_1A_STEPS = ["terraform_plan", "terraform_apply"]


@celery_app.task(bind=True, name="tasks.run_server_build", max_retries=0)
def run_server_build(self, server_request_id: str) -> dict:
    """Main entry point for provisioning a server."""
    logger.info("Starting server build for request %s", server_request_id)

    # Mark as provisioning and create build step records
    with get_sync_db() as session:
        update_server_status(
            session,
            server_request_id,
            status="provisioning",
        )
        step_records = create_build_steps(
            session, server_request_id, PHASE_1A_STEPS
        )
        step_ids = {rec["step_name"]: rec["id"] for rec in step_records}

    try:
        # Plan
        logger.info("Running terraform_plan for %s", server_request_id)
        plan_result = terraform_plan(server_request_id, step_ids["terraform_plan"])
        if plan_result["exit_code"] != 0:
            raise RuntimeError(
                f"terraform plan failed (exit {plan_result['exit_code']}): "
                f"{plan_result['output'][-500:]}"
            )

        # Apply
        logger.info("Running terraform_apply for %s", server_request_id)
        apply_result = terraform_apply(server_request_id, step_ids["terraform_apply"])
        if apply_result["exit_code"] != 0:
            raise RuntimeError(
                f"terraform apply failed (exit {apply_result['exit_code']}): "
                f"{apply_result['output'][-500:]}"
            )

        # Record success
        outputs = apply_result.get("outputs", {})
        with get_sync_db() as session:
            update_server_status(
                session,
                server_request_id,
                status="ready",
                aws_instance_id=outputs.get("instance_id"),
                private_ip=outputs.get("private_ip"),
                public_ip=outputs.get("public_ip"),
                dns_name=outputs.get("dns_name"),
            )

        logger.info(
            "Server build completed for %s (instance %s)",
            server_request_id,
            outputs.get("instance_id"),
        )
        return {
            "status": "ready",
            "server_request_id": server_request_id,
            "outputs": outputs,
        }

    except Exception as exc:
        logger.exception("Server build failed for %s: %s", server_request_id, exc)

        with get_sync_db() as session:
            update_server_status(
                session,
                server_request_id,
                status="failed",
                status_message=str(exc)[:500],
            )

        # Rollback — attempt terraform destroy
        try:
            logger.info("Initiating rollback for %s", server_request_id)
            terraform_destroy(server_request_id)
        except Exception as rollback_exc:
            logger.exception("Rollback failed for %s: %s", server_request_id, rollback_exc)

        return {
            "status": "failed",
            "server_request_id": server_request_id,
            "error": str(exc)[:2000],
        }
