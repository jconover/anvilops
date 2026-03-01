"""Unit tests for decommission task helper functions and constants.

Tests _run_puppet_purge, _run_awx_decommission, _run_terraform_destroy,
_run_dns_cleanup, _clear_server_metadata, DECOM_STEPS, and
DECOMMISSIONABLE_STATUSES. All DB and service calls are mocked.
"""

from unittest.mock import MagicMock, patch

from app.tasks.decommission import (
    DECOM_STEPS,
    DECOMMISSIONABLE_STATUSES,
    _clear_server_metadata,
    _run_awx_decommission,
    _run_dns_cleanup,
    _run_puppet_purge,
    _run_terraform_destroy,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestDecomConstants:
    def test_decom_steps_in_correct_order(self):
        assert DECOM_STEPS == [
            "puppet_purge",
            "awx_decommission",
            "terraform_destroy",
            "dns_cleanup",
        ]

    def test_decommissionable_statuses_contains_ready(self):
        assert "ready" in DECOMMISSIONABLE_STATUSES

    def test_decommissionable_statuses_contains_failed(self):
        assert "failed" in DECOMMISSIONABLE_STATUSES

    def test_decommissionable_statuses_does_not_contain_building(self):
        assert "building" not in DECOMMISSIONABLE_STATUSES

    def test_decommissionable_statuses_does_not_contain_pending(self):
        assert "pending" not in DECOMMISSIONABLE_STATUSES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_sync_session():
    session = MagicMock()
    session.__enter__ = MagicMock(return_value=session)
    session.__exit__ = MagicMock(return_value=False)
    return session


def _patch_db(session=None):
    if session is None:
        session = _make_sync_session()
    return patch("app.tasks.decommission.get_sync_db", return_value=session)


# ---------------------------------------------------------------------------
# _run_puppet_purge
# ---------------------------------------------------------------------------


class TestRunPuppetPurge:
    def test_puppet_task_none_returns_success_skipped(self):
        import app.tasks.decommission as decom_mod
        original = decom_mod.puppet_decommission
        decom_mod.puppet_decommission = None
        try:
            with _patch_db():
                result = _run_puppet_purge("sr-001", "step-001")
        finally:
            decom_mod.puppet_decommission = original
        assert result["exit_code"] == 0
        assert "skipping" in result["output"].lower()

    def test_puppet_task_success_returns_result(self):
        mock_task = MagicMock(return_value={"exit_code": 0, "output": "Purge OK"})
        import app.tasks.decommission as decom_mod
        original = decom_mod.puppet_decommission
        decom_mod.puppet_decommission = mock_task
        try:
            with _patch_db():
                result = _run_puppet_purge("sr-001", "step-001")
        finally:
            decom_mod.puppet_decommission = original
        assert result["exit_code"] == 0
        assert result["output"] == "Purge OK"

    def test_puppet_task_failure_is_best_effort(self):
        mock_task = MagicMock(return_value={"exit_code": 1, "output": "Purge failed"})
        import app.tasks.decommission as decom_mod
        original = decom_mod.puppet_decommission
        decom_mod.puppet_decommission = mock_task
        try:
            with _patch_db():
                result = _run_puppet_purge("sr-001", "step-001")
        finally:
            decom_mod.puppet_decommission = original
        # Best-effort: should still return the result dict (not raise)
        assert result["exit_code"] == 1

    def test_puppet_task_exception_returns_error(self):
        mock_task = MagicMock(side_effect=Exception("PE connection error"))
        import app.tasks.decommission as decom_mod
        original = decom_mod.puppet_decommission
        decom_mod.puppet_decommission = mock_task
        try:
            with _patch_db():
                result = _run_puppet_purge("sr-001", "step-001")
        finally:
            decom_mod.puppet_decommission = original
        assert result["exit_code"] == 1
        assert "PE connection error" in result["output"]


# ---------------------------------------------------------------------------
# _run_awx_decommission
# ---------------------------------------------------------------------------


class TestRunAwxDecommission:
    def test_awx_task_none_returns_success_skipped(self):
        import app.tasks.decommission as decom_mod
        original = decom_mod.awx_decommission
        decom_mod.awx_decommission = None
        try:
            with _patch_db():
                result = _run_awx_decommission("sr-001", "step-002")
        finally:
            decom_mod.awx_decommission = original
        assert result["exit_code"] == 0
        assert "skipping" in result["output"].lower()

    def test_awx_task_success_returns_result(self):
        mock_task = MagicMock(return_value={"exit_code": 0, "output": "AWX OK"})
        import app.tasks.decommission as decom_mod
        original = decom_mod.awx_decommission
        decom_mod.awx_decommission = mock_task
        try:
            with _patch_db():
                result = _run_awx_decommission("sr-001", "step-002")
        finally:
            decom_mod.awx_decommission = original
        assert result["exit_code"] == 0

    def test_awx_task_exception_returns_error(self):
        mock_task = MagicMock(side_effect=Exception("AWX unreachable"))
        import app.tasks.decommission as decom_mod
        original = decom_mod.awx_decommission
        decom_mod.awx_decommission = mock_task
        try:
            with _patch_db():
                result = _run_awx_decommission("sr-001", "step-002")
        finally:
            decom_mod.awx_decommission = original
        assert result["exit_code"] == 1
        assert "AWX unreachable" in result["output"]


# ---------------------------------------------------------------------------
# _run_terraform_destroy
# ---------------------------------------------------------------------------


class TestRunTerraformDestroy:
    def test_terraform_task_none_returns_failure(self):
        import app.tasks.decommission as decom_mod
        original = decom_mod.terraform_destroy
        decom_mod.terraform_destroy = None
        try:
            with _patch_db():
                result = _run_terraform_destroy("sr-001", "step-003")
        finally:
            decom_mod.terraform_destroy = original
        # terraform_destroy=None is a hard failure (not best-effort)
        assert result["exit_code"] == 1

    def test_terraform_task_success_returns_result(self):
        mock_task = MagicMock(return_value={"exit_code": 0, "output": "Destroy OK"})
        import app.tasks.decommission as decom_mod
        original = decom_mod.terraform_destroy
        decom_mod.terraform_destroy = mock_task
        try:
            with _patch_db():
                result = _run_terraform_destroy("sr-001", "step-003")
        finally:
            decom_mod.terraform_destroy = original
        assert result["exit_code"] == 0

    def test_terraform_task_failure_propagates_exit_code(self):
        mock_task = MagicMock(return_value={"exit_code": 1, "output": "Destroy failed"})
        import app.tasks.decommission as decom_mod
        original = decom_mod.terraform_destroy
        decom_mod.terraform_destroy = mock_task
        try:
            with _patch_db():
                result = _run_terraform_destroy("sr-001", "step-003")
        finally:
            decom_mod.terraform_destroy = original
        assert result["exit_code"] == 1

    def test_terraform_task_exception_returns_error(self):
        mock_task = MagicMock(side_effect=Exception("TF error"))
        import app.tasks.decommission as decom_mod
        original = decom_mod.terraform_destroy
        decom_mod.terraform_destroy = mock_task
        try:
            with _patch_db():
                result = _run_terraform_destroy("sr-001", "step-003")
        finally:
            decom_mod.terraform_destroy = original
        assert result["exit_code"] == 1
        assert "TF error" in result["output"]


# ---------------------------------------------------------------------------
# _run_dns_cleanup
# ---------------------------------------------------------------------------


class TestRunDnsCleanup:
    def _make_session_with_server(self, **overrides):
        session = _make_sync_session()
        server_data = {
            "server_name": "PROD-WEB-01",
            "dns_name": "prod-web-01.corp.com",
            "private_ip": "10.0.1.5",
            "public_ip": None,
            **overrides,
        }
        # get_server_request is called inside get_sync_db context
        # We patch get_server_request directly
        return session, server_data

    def test_dns_cleanup_success(self):
        _, server_data = self._make_session_with_server()
        with _patch_db():
            with patch(
                "app.tasks.decommission.get_server_request",
                return_value=server_data,
            ):
                result = _run_dns_cleanup("sr-001", "step-004")
        assert result["exit_code"] == 0

    def test_dns_cleanup_output_contains_server_name(self):
        _, server_data = self._make_session_with_server(server_name="MY-SRV-01")
        with _patch_db():
            with patch(
                "app.tasks.decommission.get_server_request",
                return_value=server_data,
            ):
                result = _run_dns_cleanup("sr-001", "step-004")
        assert "MY-SRV-01" in result["output"]

    def test_dns_cleanup_exception_returns_error(self):
        _, server_data = self._make_session_with_server()
        with _patch_db():
            with patch(
                "app.tasks.decommission.get_server_request",
                return_value=server_data,
            ):
                with patch(
                    "app.services.dns.DNSCleanupService.cleanup_records",
                    side_effect=Exception("DNS error"),
                ):
                    result = _run_dns_cleanup("sr-001", "step-004")
        assert result["exit_code"] == 1


# ---------------------------------------------------------------------------
# _clear_server_metadata
# ---------------------------------------------------------------------------


class TestClearServerMetadata:
    def test_clears_aws_instance_id(self):
        sr = MagicMock()
        sr.aws_instance_id = "i-abc"
        sr.private_ip = "10.0.0.1"
        sr.public_ip = "1.2.3.4"
        sr.dns_name = "srv.corp.com"
        session = _make_sync_session()
        session.get = MagicMock(return_value=sr)
        with patch("app.tasks.decommission.get_sync_db", return_value=session):
            _clear_server_metadata("sr-001")
        assert sr.aws_instance_id is None

    def test_clears_all_ip_and_dns_fields(self):
        sr = MagicMock()
        session = _make_sync_session()
        session.get = MagicMock(return_value=sr)
        with patch("app.tasks.decommission.get_sync_db", return_value=session):
            _clear_server_metadata("sr-001")
        assert sr.private_ip is None
        assert sr.public_ip is None
        assert sr.dns_name is None

    def test_clears_puppet_fields(self):
        sr = MagicMock()
        session = _make_sync_session()
        session.get = MagicMock(return_value=sr)
        with patch("app.tasks.decommission.get_sync_db", return_value=session):
            _clear_server_metadata("sr-001")
        assert sr.puppet_certname is None
        assert sr.puppet_node_group_id is None

    def test_clears_awx_fields(self):
        sr = MagicMock()
        session = _make_sync_session()
        session.get = MagicMock(return_value=sr)
        with patch("app.tasks.decommission.get_sync_db", return_value=session):
            _clear_server_metadata("sr-001")
        assert sr.awx_host_id is None

    def test_noop_when_server_not_found(self, caplog):
        import logging
        session = _make_sync_session()
        session.get = MagicMock(return_value=None)
        with patch("app.tasks.decommission.get_sync_db", return_value=session):
            with caplog.at_level(logging.ERROR):
                _clear_server_metadata("missing-id")
        assert "ServerRequest not found" in caplog.text
