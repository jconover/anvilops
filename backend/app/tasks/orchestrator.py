"""
Main build orchestration task for AnvilOps.

Coordinates the full server provisioning workflow:
  1. Load the server request from the database
  2. Create build step records for tracking
  3. Run terraform plan and apply  (status: "provisioning")
  4. Run AWX configuration pipeline (status: "configuring")
  5. Enroll in Puppet Enterprise    (status: "validating")
  6. Run final validation checks    (status: "validating")
  7. On success, mark "ready"
  8. On TF/AWX failure, trigger rollback via terraform destroy
  9. On Puppet failure, mark failed but do NOT destroy infrastructure
"""

import logging
from datetime import datetime, timezone

from app.worker.celery_app import celery_app
from app.services.db import get_sync_db, update_server_status, create_build_steps
from app.tasks.terraform import terraform_plan, terraform_apply, terraform_destroy
from app.tasks.awx import awx_configure

try:
    from app.tasks.puppet import puppet_enroll
except ImportError:
    puppet_enroll = None  # type: ignore[assignment]

try:
    from app.tasks.validation import run_validation
except ImportError:
    run_validation = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

BUILD_STEPS = [
    "terraform_plan",
    "terraform_apply",
    "awx_configure",
    "puppet_enroll",
    "validation",
]


class _PuppetEnrollmentError(Exception):
    """Raised when Puppet enrollment fails.

    Separated from generic exceptions so the orchestrator can
    distinguish Puppet failures (no infra rollback needed) from
    Terraform/AWX failures (rollback required).
    """


@celery_app.task(bind=True, name="tasks.run_server_build", max_retries=0)
def run_server_build(self, server_request_id: str) -> dict:
    """Main entry point for provisioning a server.

    Executes the full build pipeline:
      Terraform plan -> Terraform apply -> AWX configuration ->
      Puppet enrollment -> Validation.

    On Terraform or AWX failure the orchestrator marks the server
    request as "failed", attempts a Terraform destroy for rollback,
    and returns an error dict.

    On Puppet enrollment failure the server is marked as "failed" but
    infrastructure is NOT destroyed -- the server is provisioned and
    configured, just not enrolled in Puppet, which is a less severe
    failure.

    The validation step is advisory and never blocks the build.
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

    # Track outputs across stages so we can include them in the final result.
    outputs: dict = {}
    awx_host_id = None
    puppet_certname = None

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

        # Store the AWX host ID on the server request.
        awx_host_id = awx_result.get("host_id")
        with get_sync_db() as session:
            extra_fields = {}
            if awx_host_id is not None:
                extra_fields["awx_host_id"] = awx_host_id
            update_server_status(
                session,
                server_request_id,
                status="validating",
                **extra_fields,
            )

        logger.info(
            "AWX configuration succeeded for %s (awx_host %s), moving to Puppet enrollment",
            server_request_id,
            awx_host_id,
        )

        # ------------------------------------------------------------------
        # Puppet Enrollment
        # ------------------------------------------------------------------
        if puppet_enroll is not None:
            logger.info("Running puppet_enroll for %s", server_request_id)
            puppet_result = puppet_enroll(
                server_request_id, step_ids["puppet_enroll"]
            )
            puppet_certname = puppet_result.get("certname")

            if puppet_result["exit_code"] != 0:
                raise _PuppetEnrollmentError(
                    f"Puppet enrollment failed: {puppet_result['output'][-500:]}"
                )

            logger.info(
                "Puppet enrollment succeeded for %s (certname=%s)",
                server_request_id,
                puppet_certname,
            )
        else:
            logger.warning(
                "puppet_enroll task not available; skipping Puppet enrollment for %s",
                server_request_id,
            )
            # Mark the puppet_enroll build step as skipped
            with get_sync_db() as session:
                from app.services.db import update_build_step

                update_build_step(
                    session,
                    step_ids["puppet_enroll"],
                    status="completed",
                    output_log="Puppet enrollment skipped: task module not available",
                    completed_at=datetime.now(timezone.utc),
                )

        # ------------------------------------------------------------------
        # Validation
        # ------------------------------------------------------------------
        if run_validation is not None:
            logger.info("Running validation for %s", server_request_id)
            validation_result = run_validation(
                server_request_id, step_ids["validation"]
            )

            # Validation is advisory -- log the result but do not fail
            # the build regardless of exit_code.
            if validation_result["exit_code"] != 0:
                logger.warning(
                    "Validation completed with warnings for %s: %s",
                    server_request_id,
                    validation_result["output"][:500],
                )
            else:
                logger.info(
                    "All validation checks passed for %s",
                    server_request_id,
                )
        else:
            logger.warning(
                "run_validation task not available; skipping validation for %s",
                server_request_id,
            )
            # Mark the validation build step as skipped
            with get_sync_db() as session:
                from app.services.db import update_build_step

                update_build_step(
                    session,
                    step_ids["validation"],
                    status="completed",
                    output_log="Validation skipped: task module not available",
                    completed_at=datetime.now(timezone.utc),
                )

        # ------------------------------------------------------------------
        # All steps completed -- mark as ready
        # ------------------------------------------------------------------
        with get_sync_db() as session:
            update_server_status(
                session,
                server_request_id,
                status="ready",
            )

        logger.info(
            "Server build completed for %s (instance %s, awx_host %s, puppet %s)",
            server_request_id,
            outputs.get("instance_id"),
            awx_host_id,
            puppet_certname,
        )
        return {
            "status": "ready",
            "server_request_id": server_request_id,
            "outputs": outputs,
            "awx_host_id": awx_host_id,
            "puppet_certname": puppet_certname,
        }

    except _PuppetEnrollmentError as exc:
        # Puppet enrollment failed.  The server is provisioned and
        # configured (Terraform + AWX succeeded), so we do NOT trigger
        # a terraform destroy rollback.  This is a less severe failure.
        logger.exception(
            "Puppet enrollment failed for %s (no rollback): %s",
            server_request_id,
            exc,
        )

        with get_sync_db() as session:
            update_server_status(
                session,
                server_request_id,
                status="failed",
                status_message=f"Puppet enrollment failed: {str(exc)[:450]}",
            )

        return {
            "status": "failed",
            "server_request_id": server_request_id,
            "error": str(exc)[:2000],
            "outputs": outputs,
            "awx_host_id": awx_host_id,
            "puppet_certname": puppet_certname,
            "rollback": False,
        }

    except Exception as exc:
        # Terraform or AWX failure -- rollback infrastructure.
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
            "rollback": True,
        }
