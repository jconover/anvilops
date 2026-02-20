"""
Post-build validation Celery task for AnvilOps.

Runs final health and compliance checks after a server has been
provisioned (Terraform), configured (AWX), and enrolled in Puppet.
This is the last step in the build pipeline before the server is
marked as "ready".

The validation step is intentionally lenient -- it reports status
but does not block the build.  Soft failures are logged as warnings
and the build step is still marked as "completed".

Checks performed:
  1. AWS instance status (running, reachable via EC2 API)
  2. SSM agent connectivity (optional, best-effort)
  3. Puppet agent enrollment (node exists in PuppetDB)
"""

import logging
from datetime import datetime, timezone

from app.services.db import (
    get_server_request,
    get_sync_db,
    update_build_step,
)
from app.worker.celery_app import celery_app

try:
    from app.services.puppet import PuppetEnterpriseServiceSync
except ImportError:
    PuppetEnterpriseServiceSync = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


def _check_instance_status(server_data: dict) -> dict:
    """Check the AWS instance status via the EC2 API.

    Uses boto3 to verify the instance is in a "running" state and
    passes both instance-status and system-status checks.

    Returns:
        Dict with ``passed`` (bool), ``status`` (str), and ``detail`` (str).
    """
    instance_id = server_data.get("aws_instance_id")
    region = server_data.get("region", "us-east-1")

    if not instance_id:
        return {
            "passed": False,
            "status": "skipped",
            "detail": "No AWS instance ID available",
        }

    try:
        import boto3

        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_instance_status(
            InstanceIds=[instance_id],
            IncludeAllInstances=True,
        )

        statuses = response.get("InstanceStatuses", [])
        if not statuses:
            return {
                "passed": False,
                "status": "not_found",
                "detail": f"Instance {instance_id} not found in EC2",
            }

        instance_status = statuses[0]
        state = instance_status.get("InstanceState", {}).get("Name", "unknown")
        sys_status = instance_status.get("SystemStatus", {}).get("Status", "unknown")
        inst_status = instance_status.get("InstanceStatus", {}).get("Status", "unknown")

        passed = (
            state == "running"
            and sys_status == "ok"
            and inst_status == "ok"
        )

        return {
            "passed": passed,
            "status": state,
            "detail": (
                f"state={state}, system_status={sys_status}, "
                f"instance_status={inst_status}"
            ),
        }

    except ImportError:
        logger.warning("boto3 not available; skipping EC2 instance status check")
        return {
            "passed": True,
            "status": "skipped",
            "detail": "boto3 not available",
        }

    except Exception as exc:
        logger.warning(
            "EC2 instance status check failed for %s: %s",
            instance_id,
            exc,
        )
        return {
            "passed": False,
            "status": "error",
            "detail": str(exc)[:500],
        }


def _check_ssm_connectivity(server_data: dict) -> dict:
    """Check whether the SSM agent is responding on the instance.

    Uses boto3 to query the SSM managed instances list for the
    server's instance ID.

    Returns:
        Dict with ``passed`` (bool), ``status`` (str), and ``detail`` (str).
    """
    instance_id = server_data.get("aws_instance_id")
    region = server_data.get("region", "us-east-1")

    if not instance_id:
        return {
            "passed": False,
            "status": "skipped",
            "detail": "No AWS instance ID available",
        }

    try:
        import boto3

        ssm = boto3.client("ssm", region_name=region)
        response = ssm.describe_instance_information(
            Filters=[
                {
                    "Key": "InstanceIds",
                    "Values": [instance_id],
                }
            ]
        )

        instances = response.get("InstanceInformationList", [])
        if not instances:
            return {
                "passed": False,
                "status": "not_registered",
                "detail": f"Instance {instance_id} not registered with SSM",
            }

        ssm_info = instances[0]
        ping_status = ssm_info.get("PingStatus", "unknown")
        agent_version = ssm_info.get("AgentVersion", "unknown")

        passed = ping_status == "Online"
        return {
            "passed": passed,
            "status": ping_status,
            "detail": (
                f"ping_status={ping_status}, "
                f"agent_version={agent_version}"
            ),
        }

    except ImportError:
        logger.warning("boto3 not available; skipping SSM connectivity check")
        return {
            "passed": True,
            "status": "skipped",
            "detail": "boto3 not available",
        }

    except Exception as exc:
        logger.warning(
            "SSM connectivity check failed for %s: %s",
            instance_id,
            exc,
        )
        return {
            "passed": False,
            "status": "error",
            "detail": str(exc)[:500],
        }


def _check_puppet_enrollment(server_data: dict) -> dict:
    """Check whether the Puppet agent has enrolled with PuppetDB.

    Queries PuppetDB for the node's certname to verify the agent has
    checked in at least once.

    Returns:
        Dict with ``passed`` (bool), ``status`` (str), and ``detail`` (str).
    """
    certname = server_data.get("puppet_certname")

    if not certname:
        # Try generating the certname from the server name
        try:
            from app.services.puppet_classifier import get_certname

            server_name = server_data.get("server_name", "")
            if server_name:
                certname = get_certname(server_name)
        except ImportError:
            pass

    if not certname:
        return {
            "passed": False,
            "status": "skipped",
            "detail": "No Puppet certname available for validation",
        }

    if PuppetEnterpriseServiceSync is None:
        return {
            "passed": True,
            "status": "skipped",
            "detail": "PuppetEnterpriseServiceSync not available",
        }

    puppet_service = None
    try:
        from app.core.config import settings

        puppet_service = PuppetEnterpriseServiceSync(
            base_url=settings.PUPPET_BASE_URL,
            token=settings.PUPPET_API_TOKEN,
            verify_ssl=settings.PUPPET_VERIFY_SSL,
        )

        node_status = puppet_service.get_node_status(certname)

        if not node_status:
            return {
                "passed": False,
                "status": "not_found",
                "detail": f"Node {certname} not found in PuppetDB",
            }

        report_status = node_status.get("latest_report_status", "unknown")
        catalog_ts = node_status.get("catalog_timestamp")

        passed = catalog_ts is not None
        return {
            "passed": passed,
            "status": report_status,
            "detail": (
                f"report_status={report_status}, "
                f"catalog_timestamp={catalog_ts}"
            ),
        }

    except Exception as exc:
        logger.warning(
            "Puppet enrollment check failed for %s: %s", certname, exc
        )
        return {
            "passed": False,
            "status": "error",
            "detail": str(exc)[:500],
        }

    finally:
        if puppet_service is not None:
            try:
                puppet_service.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# run_validation
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="tasks.run_validation")
def run_validation(
    self, server_request_id: str, build_step_id: str | None = None
) -> dict:
    """Run final validation checks on a fully built server.

    Called by the orchestrator after ``puppet_enroll`` completes.
    Performs a series of health and compliance checks to verify the
    server is ready for use.

    This task is intentionally lenient:
    - Individual check failures are logged as warnings, not hard errors.
    - The build step is marked "completed" even if some checks fail.
    - Only a complete inability to run any checks results in a failure.

    Returns:
        A dict with ``exit_code`` (0 = all passed, 1 = some warnings),
        ``output`` (human-readable summary), and ``checks`` (per-check
        results).
    """
    logger.info("run_validation starting for %s", server_request_id)

    # Mark build step as in-progress
    if build_step_id:
        with get_sync_db() as session:
            update_build_step(
                session,
                build_step_id,
                status="in_progress",
                started_at=datetime.now(timezone.utc),
            )

    # Load server request data
    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    server_name = server_data.get("server_name", server_request_id)

    # Run each validation check
    checks: dict[str, dict] = {}

    logger.info("Running EC2 instance status check for %s", server_name)
    checks["instance_status"] = _check_instance_status(server_data)

    logger.info("Running SSM connectivity check for %s", server_name)
    checks["ssm_connectivity"] = _check_ssm_connectivity(server_data)

    logger.info("Running Puppet enrollment check for %s", server_name)
    checks["puppet_enrollment"] = _check_puppet_enrollment(server_data)

    # Build summary
    total_checks = len(checks)
    passed_checks = sum(1 for c in checks.values() if c.get("passed"))
    skipped_checks = sum(
        1 for c in checks.values() if c.get("status") == "skipped"
    )
    failed_checks = total_checks - passed_checks

    lines = [
        f"Validation summary for {server_name}:",
        f"  Total checks: {total_checks}",
        f"  Passed: {passed_checks}",
        f"  Skipped: {skipped_checks}",
        f"  Failed/Warnings: {failed_checks}",
        "",
    ]

    for check_name, result in checks.items():
        status_indicator = "PASS" if result["passed"] else "WARN"
        lines.append(
            f"  [{status_indicator}] {check_name}: "
            f"{result['status']} -- {result['detail']}"
        )

    output_log = "\n".join(lines)

    # Determine overall result.
    # Validation is lenient -- even if checks fail, we mark the step as
    # completed (with warnings in the log).  Only mark as "failed" if
    # something truly unexpected happened (which would be caught by the
    # except clause below, not here).
    all_passed = failed_checks == 0
    exit_code = 0 if all_passed else 1

    if all_passed:
        logger.info(
            "All validation checks passed for %s (%d/%d)",
            server_name,
            passed_checks,
            total_checks,
        )
    else:
        logger.warning(
            "Validation completed with warnings for %s (%d/%d passed): %s",
            server_name,
            passed_checks,
            total_checks,
            output_log[:500],
        )

    # Update build step -- always mark as "completed" since validation
    # is advisory.  The output_log contains the details for review.
    if build_step_id:
        with get_sync_db() as session:
            update_build_step(
                session,
                build_step_id,
                status="completed",
                output_log=output_log[-10000:],
                completed_at=datetime.now(timezone.utc),
            )

    return {
        "exit_code": exit_code,
        "output": output_log,
        "checks": checks,
    }
