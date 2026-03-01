"""Tests for the main build orchestration task (app.tasks.orchestrator).

All external dependencies (database, Terraform, AWX, Puppet) are mocked.
These tests verify the orchestrator's control flow, status transitions,
and error handling/rollback logic.
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STEP_IDS = {
    "terraform_plan": "step-plan-id",
    "terraform_apply": "step-apply-id",
    "awx_configure": "step-awx-id",
    "puppet_enroll": "step-puppet-id",
    "validation": "step-validation-id",
}


def _mock_db_context():
    """Return a mock get_sync_db that yields a session context manager."""
    session = MagicMock()
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=session)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx, session


def _build_step_records():
    return [{"step_name": k, "id": v} for k, v in _STEP_IDS.items()]


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRunServerBuildSuccess:
    """Full successful build pipeline."""

    @patch("app.tasks.orchestrator.run_validation")
    @patch("app.tasks.orchestrator.puppet_enroll")
    @patch("app.tasks.orchestrator.awx_configure")
    @patch("app.tasks.orchestrator.terraform_apply")
    @patch("app.tasks.orchestrator.terraform_plan")
    @patch("app.tasks.orchestrator.create_build_steps")
    @patch("app.tasks.orchestrator.update_server_status")
    @patch("app.tasks.orchestrator.get_sync_db")
    def test_happy_path_returns_ready(
        self, mock_db, mock_update, mock_steps,
        mock_tf_plan, mock_tf_apply, mock_awx, mock_puppet, mock_validate,
    ):
        ctx, session = _mock_db_context()
        mock_db.return_value = ctx
        mock_steps.return_value = _build_step_records()

        mock_tf_plan.return_value = {"exit_code": 0, "output": "ok"}
        mock_tf_apply.return_value = {
            "exit_code": 0,
            "output": "ok",
            "outputs": {
                "instance_id": "i-abc123",
                "private_ip": "10.0.0.1",
                "public_ip": None,
                "dns_name": "web01.internal",
            },
        }
        mock_awx.return_value = {"exit_code": 0, "output": "ok", "host_id": 42}
        mock_puppet.return_value = {
            "exit_code": 0,
            "output": "ok",
            "certname": "web01.anvilops.internal",
        }
        mock_validate.return_value = {"exit_code": 0, "output": "all checks passed"}

        from app.tasks.orchestrator import run_server_build

        result = run_server_build("req-123")

        assert result["status"] == "ready"
        assert result["server_request_id"] == "req-123"
        assert result["outputs"]["instance_id"] == "i-abc123"
        assert result["awx_host_id"] == 42
        assert result["puppet_certname"] == "web01.anvilops.internal"


# ---------------------------------------------------------------------------
# Terraform failures trigger rollback
# ---------------------------------------------------------------------------


class TestRunServerBuildTerraformFailure:
    """Terraform plan/apply failure triggers rollback via terraform_destroy."""

    @patch("app.tasks.orchestrator.terraform_destroy")
    @patch("app.tasks.orchestrator.terraform_plan")
    @patch("app.tasks.orchestrator.create_build_steps")
    @patch("app.tasks.orchestrator.update_server_status")
    @patch("app.tasks.orchestrator.get_sync_db")
    def test_tf_plan_failure_triggers_rollback(
        self, mock_db, mock_update, mock_steps,
        mock_tf_plan, mock_tf_destroy,
    ):
        ctx, session = _mock_db_context()
        mock_db.return_value = ctx
        mock_steps.return_value = _build_step_records()
        mock_tf_plan.return_value = {"exit_code": 1, "output": "plan failed"}

        from app.tasks.orchestrator import run_server_build

        result = run_server_build("req-fail")

        assert result["status"] == "failed"
        assert result["rollback"] is True
        mock_tf_destroy.assert_called_once_with("req-fail")

    @patch("app.tasks.orchestrator.terraform_destroy")
    @patch("app.tasks.orchestrator.terraform_apply")
    @patch("app.tasks.orchestrator.terraform_plan")
    @patch("app.tasks.orchestrator.create_build_steps")
    @patch("app.tasks.orchestrator.update_server_status")
    @patch("app.tasks.orchestrator.get_sync_db")
    def test_tf_apply_failure_triggers_rollback(
        self, mock_db, mock_update, mock_steps,
        mock_tf_plan, mock_tf_apply, mock_tf_destroy,
    ):
        ctx, session = _mock_db_context()
        mock_db.return_value = ctx
        mock_steps.return_value = _build_step_records()
        mock_tf_plan.return_value = {"exit_code": 0, "output": "ok"}
        mock_tf_apply.return_value = {"exit_code": 1, "output": "apply failed"}

        from app.tasks.orchestrator import run_server_build

        result = run_server_build("req-fail-apply")

        assert result["status"] == "failed"
        assert result["rollback"] is True
        mock_tf_destroy.assert_called_once()


# ---------------------------------------------------------------------------
# AWX failure triggers rollback
# ---------------------------------------------------------------------------


class TestRunServerBuildAWXFailure:
    @patch("app.tasks.orchestrator.terraform_destroy")
    @patch("app.tasks.orchestrator.awx_configure")
    @patch("app.tasks.orchestrator.terraform_apply")
    @patch("app.tasks.orchestrator.terraform_plan")
    @patch("app.tasks.orchestrator.create_build_steps")
    @patch("app.tasks.orchestrator.update_server_status")
    @patch("app.tasks.orchestrator.get_sync_db")
    def test_awx_failure_triggers_rollback(
        self, mock_db, mock_update, mock_steps,
        mock_tf_plan, mock_tf_apply, mock_awx, mock_tf_destroy,
    ):
        ctx, session = _mock_db_context()
        mock_db.return_value = ctx
        mock_steps.return_value = _build_step_records()
        mock_tf_plan.return_value = {"exit_code": 0, "output": "ok"}
        mock_tf_apply.return_value = {
            "exit_code": 0, "output": "ok",
            "outputs": {"instance_id": "i-123"},
        }
        mock_awx.return_value = {"exit_code": 1, "output": "awx failed"}

        from app.tasks.orchestrator import run_server_build

        result = run_server_build("req-awx-fail")

        assert result["status"] == "failed"
        assert result["rollback"] is True
        mock_tf_destroy.assert_called_once()


# ---------------------------------------------------------------------------
# Puppet failure does NOT trigger rollback
# ---------------------------------------------------------------------------


class TestRunServerBuildPuppetFailure:
    @patch("app.tasks.orchestrator.puppet_enroll")
    @patch("app.tasks.orchestrator.awx_configure")
    @patch("app.tasks.orchestrator.terraform_apply")
    @patch("app.tasks.orchestrator.terraform_plan")
    @patch("app.tasks.orchestrator.create_build_steps")
    @patch("app.tasks.orchestrator.update_server_status")
    @patch("app.tasks.orchestrator.get_sync_db")
    def test_puppet_failure_no_rollback(
        self, mock_db, mock_update, mock_steps,
        mock_tf_plan, mock_tf_apply, mock_awx, mock_puppet,
    ):
        ctx, session = _mock_db_context()
        mock_db.return_value = ctx
        mock_steps.return_value = _build_step_records()
        mock_tf_plan.return_value = {"exit_code": 0, "output": "ok"}
        mock_tf_apply.return_value = {
            "exit_code": 0, "output": "ok",
            "outputs": {"instance_id": "i-123"},
        }
        mock_awx.return_value = {"exit_code": 0, "output": "ok", "host_id": 1}
        mock_puppet.return_value = {"exit_code": 1, "output": "puppet failed"}

        from app.tasks.orchestrator import run_server_build

        result = run_server_build("req-puppet-fail")

        assert result["status"] == "failed"
        assert result["rollback"] is False


# ---------------------------------------------------------------------------
# Validation is advisory (does not fail build)
# ---------------------------------------------------------------------------


class TestRunServerBuildValidationAdvisory:
    @patch("app.tasks.orchestrator.run_validation")
    @patch("app.tasks.orchestrator.puppet_enroll")
    @patch("app.tasks.orchestrator.awx_configure")
    @patch("app.tasks.orchestrator.terraform_apply")
    @patch("app.tasks.orchestrator.terraform_plan")
    @patch("app.tasks.orchestrator.create_build_steps")
    @patch("app.tasks.orchestrator.update_server_status")
    @patch("app.tasks.orchestrator.get_sync_db")
    def test_validation_failure_still_ready(
        self, mock_db, mock_update, mock_steps,
        mock_tf_plan, mock_tf_apply, mock_awx, mock_puppet, mock_validate,
    ):
        ctx, session = _mock_db_context()
        mock_db.return_value = ctx
        mock_steps.return_value = _build_step_records()
        mock_tf_plan.return_value = {"exit_code": 0, "output": "ok"}
        mock_tf_apply.return_value = {
            "exit_code": 0, "output": "ok",
            "outputs": {"instance_id": "i-123"},
        }
        mock_awx.return_value = {"exit_code": 0, "output": "ok", "host_id": 1}
        mock_puppet.return_value = {
            "exit_code": 0, "output": "ok", "certname": "web01",
        }
        # Validation fails, but build should still succeed
        mock_validate.return_value = {
            "exit_code": 1,
            "output": "check_dns: WARN - reverse DNS missing",
        }

        from app.tasks.orchestrator import run_server_build

        result = run_server_build("req-val-warn")

        assert result["status"] == "ready"


# ---------------------------------------------------------------------------
# BUILD_STEPS constant
# ---------------------------------------------------------------------------


class TestBuildStepsConstant:
    def test_build_steps_order(self):
        from app.tasks.orchestrator import BUILD_STEPS

        assert BUILD_STEPS == [
            "terraform_plan",
            "terraform_apply",
            "awx_configure",
            "puppet_enroll",
            "validation",
        ]

    def test_build_steps_count(self):
        from app.tasks.orchestrator import BUILD_STEPS

        assert len(BUILD_STEPS) == 5
