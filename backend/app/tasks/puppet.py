"""
Puppet Enterprise Celery tasks for AnvilOps.

Provides tasks that drive the Puppet enrollment pipeline after AWX
configuration has bootstrapped the Puppet agent on a provisioned server.
Each task follows the same conventions as the Terraform and AWX tasks:
progress is persisted to BuildStep records, errors are captured, and
results are returned as plain dicts for JSON serialisation.

Tasks:
  - puppet_enroll      -- Enroll a node in Puppet Enterprise (Day-2 readiness).
  - puppet_decommission -- Purge a node from Puppet Enterprise during teardown.
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
    from app.services.puppet_exceptions import PuppetError
except ImportError:
    PuppetEnterpriseServiceSync = None  # type: ignore[assignment,misc]
    PuppetError = Exception  # type: ignore[assignment,misc]

try:
    from app.services.puppet_classifier import get_certname
except ImportError:
    get_certname = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _get_puppet_service() -> "PuppetEnterpriseServiceSync":
    """Construct a synchronous Puppet Enterprise client using application settings."""
    if PuppetEnterpriseServiceSync is None:
        raise RuntimeError(
            "PuppetEnterpriseServiceSync is not available -- "
            "ensure app.services.puppet is installed"
        )
    from app.core.config import settings

    return PuppetEnterpriseServiceSync(
        base_url=settings.PUPPET_BASE_URL,
        token=settings.PUPPET_API_TOKEN,
        verify_ssl=settings.PUPPET_VERIFY_SSL,
    )


# ---------------------------------------------------------------------------
# puppet_enroll
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="tasks.puppet_enroll")
def puppet_enroll(
    self, server_request_id: str, build_step_id: str | None = None
) -> dict:
    """Enroll a provisioned and configured server in Puppet Enterprise.

    Called by the orchestrator after ``awx_configure`` succeeds.  The task:

    1. Loads the server request from the database.
    2. Marks the build step as *in_progress*.
    3. Generates the Puppet certname from the server name.
    4. Delegates to ``PuppetEnterpriseServiceSync.enroll_node`` which
       handles node group creation, node pinning, certificate signing,
       and waiting for the first Puppet run.
    5. On success, stores ``puppet_certname`` and ``puppet_node_group_id``
       on the server request.
    6. Records success or failure on the build step.

    Returns:
        A dict with ``exit_code`` (0 = success, 1 = failure), ``output``
        (human-readable log), and ``certname`` (the Puppet certname).
    """
    logger.info("puppet_enroll starting for %s", server_request_id)

    # Mark build step as in-progress
    if build_step_id:
        with get_sync_db() as session:
            update_build_step(
                session,
                build_step_id,
                status="in_progress",
                started_at=datetime.now(timezone.utc),
            )

    # Load latest server request data
    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    server_name = server_data["server_name"]
    puppet_role = server_data.get("puppet_role", "base")
    environment = server_data.get("environment", "production")

    # Generate the Puppet certname
    if get_certname is not None:
        certname = get_certname(server_name)
    else:
        # Fallback: lowercase FQDN-style certname
        certname = f"{server_name.lower()}.anvilops.internal"

    logger.info(
        "Enrolling %s in Puppet Enterprise (certname=%s, role=%s, env=%s)",
        server_name,
        certname,
        puppet_role,
        environment,
    )

    puppet_service = _get_puppet_service()
    try:
        enroll_result = puppet_service.enroll_node(
            certname=certname,
            puppet_role=puppet_role,
            environment=environment,
        )

        success = enroll_result.get("success", False)
        node_group_id = enroll_result.get("node_group_id")
        report_status = enroll_result.get("report_status", "unknown")

        if success:
            output_log = (
                f"Puppet enrollment succeeded for {server_name}\n"
                f"Certname: {certname}\n"
                f"Node group: {enroll_result.get('node_group', 'unknown')}\n"
                f"Node group ID: {node_group_id}\n"
                f"Report status: {report_status}"
            )
        else:
            output_log = (
                f"Puppet enrollment FAILED for {server_name}\n"
                f"Certname: {certname}\n"
                f"Report status: {report_status}\n"
                f"Error: {enroll_result.get('error', 'unknown')}"
            )

        # Persist Puppet metadata on the server request
        if node_group_id or certname:
            with get_sync_db() as session:
                extra_fields = {"puppet_certname": certname}
                if node_group_id:
                    extra_fields["puppet_node_group_id"] = node_group_id
                if report_status and report_status not in ("unknown", "error", "timeout"):
                    extra_fields["puppet_last_report_status"] = report_status
                if success:
                    extra_fields["puppet_enrolled_at"] = datetime.now(timezone.utc)

                # Update puppet metadata on the server request without
                # changing the status (the orchestrator manages status
                # transitions).
                from app.models.server import ServerRequest

                sr = session.get(ServerRequest, server_request_id)
                if sr is not None:
                    for key, value in extra_fields.items():
                        if hasattr(sr, key):
                            setattr(sr, key, value)
                    sr.updated_at = datetime.now(timezone.utc)

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
                "Puppet enrollment failed for %s: %s",
                server_request_id,
                output_log[:500],
            )
        else:
            logger.info(
                "Puppet enrollment completed for %s (certname=%s, group=%s)",
                server_request_id,
                certname,
                node_group_id,
            )

        return {
            "exit_code": exit_code,
            "output": output_log,
            "certname": certname,
            "node_group_id": node_group_id,
        }

    except Exception as exc:
        logger.exception("puppet_enroll error for %s: %s", server_request_id, exc)
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
            "output": f"Puppet enrollment error: {error_message}",
            "certname": certname,
            "node_group_id": None,
        }

    finally:
        try:
            puppet_service.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# puppet_decommission
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="tasks.puppet_decommission")
def puppet_decommission(self, server_request_id: str) -> dict:
    """Remove a server's node from Puppet Enterprise during decommission.

    Looks up the server request to find the Puppet certname (stored as
    ``puppet_certname`` on the ServerRequest model).  If present, the
    node is fully purged from Puppet Enterprise (PuppetDB deactivation,
    classifier unpin, certificate revocation and deletion).

    This task is intentionally best-effort: failures are logged but do
    not raise exceptions so that the broader decommission workflow can
    continue.

    Returns:
        A dict with ``exit_code`` and ``output``.
    """
    logger.info("puppet_decommission starting for %s", server_request_id)

    with get_sync_db() as session:
        server_data = get_server_request(session, server_request_id)

    certname = server_data.get("puppet_certname")
    server_name = server_data.get("server_name", server_request_id)

    if not certname:
        msg = (
            f"No Puppet certname recorded for {server_name} "
            f"(request {server_request_id}), skipping Puppet cleanup"
        )
        logger.info(msg)
        return {"exit_code": 0, "output": msg}

    puppet_service = _get_puppet_service()
    try:
        puppet_service.purge_node(certname)
        msg = (
            f"Purged Puppet node {certname} ({server_name}) "
            f"from Puppet Enterprise"
        )
        logger.info(msg)
        return {"exit_code": 0, "output": msg}

    except Exception as exc:
        error_msg = (
            f"Failed to purge Puppet node {certname} ({server_name}): {exc}"
        )
        logger.exception(error_msg)
        return {"exit_code": 1, "output": error_msg}

    finally:
        try:
            puppet_service.close()
        except Exception:
            pass
