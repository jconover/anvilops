"""
Main build orchestration task for AnvilOps.

Coordinates the full server provisioning workflow:
  1. Load the server request from the database
  2. Create build step records for tracking
  3. Run terraform plan and apply
  4. Run AWX configuration pipeline (Ansible Day-1 setup)
  5. On success, record AWS instance details and mark "ready"
  6. On failure, trigger rollback via terraform destroy
"""

import logging
from datetime import datetime, timezone

from app.worker.celery_app import celery_app
from app.services.db import get_sync_db, update_server_status, create_build_steps
from app.tasks.terraform import terraform_plan, terraform_apply, terraform_destroy
from app.tasks.awx import awx_configure

logger = logging.getLogger(__name__)

BUILD_STEPS = [
    "terraform_plan",
    "terraform_apply",
    "awx_configure",
]


@celery_app.task(bind=True, name="tasks.run_server_build", max_retries=0)
def run_server_build(self, server_request_id: str) -> dict:
    """Main entry point for provisioning a server.

    Executes the full build pipeline: Terraform plan -> Terraform apply ->
    AWX configuration.  On any failure the orchestrator marks the server
    request as "failed", attempts a Terraform destroy for rollback, and
    returns an error dict.
    """
    logger.info("Starting server build for request %s", server_request_id)

    # Mark as provisioning and create build step records
    with get_sync_db() as session:
        update_server_status(
            session,
            server_request_id,
            status="provisioning",
        )
        step_records = create_build_steps(
            session, server_request_id, BUILD_STEPS
        )
        step_ids = {rec["step_name"]: rec["id"] for rec in step_records}

    try:
        # ------------------------------------------------------------------
        # Terraform Plan
        # ------------------------------------------------------------------
        logger.info("Running terraform_plan for %s", server_request_id)
        plan_result = terraform_plan(server_request_id, step_ids["terraform_plan"])
        if plan_result["exit_code"] != 0:
            raise RuntimeError(
                f"terraform plan failed (exit {plan_result['exit_code']}): "
                f"{plan_result['output'][-500:]}"
            )

        # ------------------------------------------------------------------
        # Terraform Apply
        # ------------------------------------------------------------------
        logger.info("Running terraform_apply for %s", server_request_id)
        apply_result = terraform_apply(server_request_id, step_ids["terraform_apply"])
        if apply_result["exit_code"] != 0:
            raise RuntimeError(
                f"terraform apply failed (exit {apply_result['exit_code']}): "
                f"{apply_result['output'][-500:]}"
            )

        # Terraform succeeded -- persist instance details and transition to
        # "configuring" so the UI can show the pipeline moving to the AWX
        # stage.
        outputs = apply_result.get("outputs", {})
        with get_sync_db() as session:
            update_server_status(
                session,
                server_request_id,
                status="configuring",
                aws_instance_id=outputs.get("instance_id"),
                private_ip=outputs.get("private_ip"),
                public_ip=outputs.get("public_ip"),
                dns_name=outputs.get("dns_name"),
            )
        logger.info(
            "Terraform apply succeeded for %s (instance %s), moving to AWX configuration",
            server_request_id,
            outputs.get("instance_id"),
        )

        # ------------------------------------------------------------------
        # AWX Configuration
        # ------------------------------------------------------------------
        logger.info("Running awx_configure for %s", server_request_id)
        awx_result = awx_configure(server_request_id, step_ids["awx_configure"])
        if awx_result["exit_code"] != 0:
            raise RuntimeError(
                f"AWX configuration failed: {awx_result['output'][-500:]}"
            )

        # Store the AWX host ID on the server request so it can be used
        # during decommission.
        awx_host_id = awx_result.get("host_id")
        with get_sync_db() as session:
            extra_fields = {}
            if awx_host_id is not None:
                extra_fields["awx_host_id"] = awx_host_id
            update_server_status(
                session,
                server_request_id,
                status="ready",
                **extra_fields,
            )

        logger.info(
            "Server build completed for %s (instance %s, awx_host %s)",
            server_request_id,
            outputs.get("instance_id"),
            awx_host_id,
        )
        return {
            "status": "ready",
            "server_request_id": server_request_id,
            "outputs": outputs,
            "awx_host_id": awx_host_id,
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

        # Rollback -- attempt terraform destroy to clean up any
        # infrastructure that was created.
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
