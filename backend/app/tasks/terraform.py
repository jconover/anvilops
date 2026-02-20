"""
Terraform-specific Celery tasks.

Each task wraps a stage of the Terraform lifecycle (plan, apply, destroy)
and persists progress to the database via BuildStep records.
"""

import logging
import os
from datetime import datetime, timezone

from app.services.db import get_server_request, get_sync_db, update_build_step
from app.services.terraform import TerraformService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)


def _get_terraform_service(environment: str) -> TerraformService:
    """Construct a TerraformService for the given environment."""
    work_dir = os.path.join(_PROJECT_ROOT, "terraform")
    return TerraformService(work_dir=work_dir, environment=environment)


@celery_app.task(bind=True, name="tasks.terraform_plan")
def terraform_plan(
    self, server_request_id: str, build_step_id: str | None = None
) -> dict:
    """Generate a Terraform plan for a server request."""
    logger.info("terraform_plan starting for %s", server_request_id)

    if build_step_id:
        with get_sync_db() as session:
            update_build_step(
                session, build_step_id,
                status="in_progress",
                started_at=datetime.now(timezone.utc),
            )

    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    environment = server_data["environment"]
    tf = _get_terraform_service(environment)
    workspace_name = f"server-{server_request_id}"

    try:
        exit_code, init_output = tf.init()
        if exit_code != 0:
            raise RuntimeError(f"terraform init failed: {init_output[-500:]}")

        tf.setup_workspace(workspace_name)
        var_file = tf.generate_tfvars(server_data)
        exit_code, plan_output = tf.plan(var_file)

        combined_output = (
            f"--- terraform init ---\n{init_output}\n"
            f"--- terraform plan ---\n{plan_output}"
        )

        if build_step_id:
            with get_sync_db() as session:
                update_build_step(
                    session, build_step_id,
                    status="completed" if exit_code == 0 else "failed",
                    output_log=combined_output[-10000:],
                    completed_at=datetime.now(timezone.utc),
                )

        return {"exit_code": exit_code, "output": combined_output}

    except Exception as exc:
        logger.exception("terraform_plan error for %s: %s", server_request_id, exc)
        if build_step_id:
            with get_sync_db() as session:
                update_build_step(
                    session, build_step_id,
                    status="failed",
                    error_message=str(exc)[:1000],
                    completed_at=datetime.now(timezone.utc),
                )
        return {"exit_code": 1, "output": str(exc)}


@celery_app.task(bind=True, name="tasks.terraform_apply")
def terraform_apply(
    self, server_request_id: str, build_step_id: str | None = None
) -> dict:
    """Run terraform apply -auto-approve for a server request."""
    logger.info("terraform_apply starting for %s", server_request_id)

    if build_step_id:
        with get_sync_db() as session:
            update_build_step(
                session, build_step_id,
                status="in_progress",
                started_at=datetime.now(timezone.utc),
            )

    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    environment = server_data["environment"]
    tf = _get_terraform_service(environment)
    workspace_name = f"server-{server_request_id}"

    try:
        tf.setup_workspace(workspace_name)
        var_file = tf.generate_tfvars(server_data)
        exit_code, apply_output, outputs = tf.apply(var_file)

        if build_step_id:
            with get_sync_db() as session:
                update_build_step(
                    session, build_step_id,
                    status="completed" if exit_code == 0 else "failed",
                    output_log=apply_output[-10000:],
                    completed_at=datetime.now(timezone.utc),
                )

        return {
            "exit_code": exit_code,
            "output": apply_output,
            "outputs": outputs,
        }

    except Exception as exc:
        logger.exception("terraform_apply error for %s: %s", server_request_id, exc)
        if build_step_id:
            with get_sync_db() as session:
                update_build_step(
                    session, build_step_id,
                    status="failed",
                    error_message=str(exc)[:1000],
                    completed_at=datetime.now(timezone.utc),
                )
        return {"exit_code": 1, "output": str(exc), "outputs": {}}


@celery_app.task(bind=True, name="tasks.terraform_destroy")
def terraform_destroy(self, server_request_id: str) -> dict:
    """Run terraform destroy -auto-approve for rollback or decommission."""
    logger.info("terraform_destroy starting for %s", server_request_id)

    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    environment = server_data["environment"]
    tf = _get_terraform_service(environment)
    workspace_name = f"server-{server_request_id}"

    try:
        exit_code, init_output = tf.init()
        if exit_code != 0:
            raise RuntimeError(f"terraform init failed: {init_output[-500:]}")

        tf.setup_workspace(workspace_name)
        var_file = tf.generate_tfvars(server_data)
        exit_code, destroy_output = tf.destroy(var_file)

        logger.info(
            "terraform_destroy finished for %s with exit_code=%d",
            server_request_id, exit_code,
        )
        return {"exit_code": exit_code, "output": destroy_output}

    except Exception as exc:
        logger.exception("terraform_destroy error for %s: %s", server_request_id, exc)
        return {"exit_code": 1, "output": str(exc)}
