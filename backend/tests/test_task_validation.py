"""Unit tests for validation task helper functions.

Tests the three check functions (_check_instance_status, _check_ssm_connectivity,
_check_puppet_enrollment) directly without invoking Celery. All boto3 and
Puppet calls are mocked.

boto3 is not installed in the dev venv, so tests that exercise the boto3
code path inject a fake boto3 module via sys.modules.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from app.tasks.validation import (
    _check_instance_status,
    _check_puppet_enrollment,
    _check_ssm_connectivity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_boto3_mock():
    """Return a minimal boto3 mock module with a configurable client factory."""
    boto3_mod = MagicMock()
    return boto3_mod


# ---------------------------------------------------------------------------
# _check_instance_status
# ---------------------------------------------------------------------------


class TestCheckInstanceStatus:
    def test_no_instance_id_returns_skipped(self):
        result = _check_instance_status({})
        assert result["passed"] is False
        assert result["status"] == "skipped"
        assert "No AWS instance ID" in result["detail"]

    def test_instance_id_none_returns_skipped(self):
        result = _check_instance_status({"aws_instance_id": None})
        assert result["passed"] is False
        assert result["status"] == "skipped"

    def test_running_instance_passes(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ec2
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_instance_status({
                "aws_instance_id": "i-abc123",
                "region": "us-east-1",
            })
        assert result["passed"] is True
        assert result["status"] == "running"

    def test_stopped_instance_fails(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "stopped"},
                    "SystemStatus": {"Status": "not-applicable"},
                    "InstanceStatus": {"Status": "not-applicable"},
                }
            ]
        }
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ec2
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_instance_status({
                "aws_instance_id": "i-abc123",
                "region": "us-east-1",
            })
        assert result["passed"] is False
        assert result["status"] == "stopped"

    def test_instance_not_found_returns_not_found(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instance_status.return_value = {"InstanceStatuses": []}
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ec2
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_instance_status({
                "aws_instance_id": "i-missing",
                "region": "us-east-1",
            })
        assert result["passed"] is False
        assert result["status"] == "not_found"

    def test_boto3_not_available_returns_skipped(self):
        """When boto3 raises ImportError, check is skipped (passed=True)."""
        # Remove boto3 from sys.modules to force ImportError inside the function
        modules_backup = sys.modules.pop("boto3", None)
        try:
            result = _check_instance_status({
                "aws_instance_id": "i-abc",
                "region": "us-east-1",
            })
        finally:
            if modules_backup is not None:
                sys.modules["boto3"] = modules_backup
        assert result["passed"] is True
        assert result["status"] == "skipped"

    def test_boto3_exception_returns_error(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instance_status.side_effect = Exception("API error")
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ec2
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_instance_status({
                "aws_instance_id": "i-abc123",
                "region": "us-east-1",
            })
        assert result["passed"] is False
        assert result["status"] == "error"
        assert "API error" in result["detail"]

    def test_detail_contains_state_info(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instance_status.return_value = {
            "InstanceStatuses": [
                {
                    "InstanceState": {"Name": "running"},
                    "SystemStatus": {"Status": "ok"},
                    "InstanceStatus": {"Status": "ok"},
                }
            ]
        }
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ec2
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_instance_status({
                "aws_instance_id": "i-abc123",
                "region": "us-east-1",
            })
        assert "state=running" in result["detail"]
        assert "system_status=ok" in result["detail"]

    def test_uses_default_region_when_not_specified(self):
        mock_ec2 = MagicMock()
        mock_ec2.describe_instance_status.return_value = {"InstanceStatuses": []}
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ec2
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            _check_instance_status({"aws_instance_id": "i-abc"})
        boto3_mod.client.assert_called_once_with("ec2", region_name="us-east-1")


# ---------------------------------------------------------------------------
# _check_ssm_connectivity
# ---------------------------------------------------------------------------


class TestCheckSsmConnectivity:
    def test_no_instance_id_returns_skipped(self):
        result = _check_ssm_connectivity({})
        assert result["passed"] is False
        assert result["status"] == "skipped"

    def test_online_agent_passes(self):
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {
            "InstanceInformationList": [
                {"PingStatus": "Online", "AgentVersion": "3.2.0"}
            ]
        }
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ssm
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_ssm_connectivity({
                "aws_instance_id": "i-abc123",
                "region": "us-east-1",
            })
        assert result["passed"] is True
        assert result["status"] == "Online"

    def test_offline_agent_fails(self):
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {
            "InstanceInformationList": [
                {"PingStatus": "Inactive", "AgentVersion": "3.2.0"}
            ]
        }
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ssm
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_ssm_connectivity({
                "aws_instance_id": "i-abc123",
                "region": "us-east-1",
            })
        assert result["passed"] is False
        assert result["status"] == "Inactive"

    def test_not_registered_returns_not_registered(self):
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {
            "InstanceInformationList": []
        }
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ssm
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_ssm_connectivity({
                "aws_instance_id": "i-missing",
                "region": "us-east-1",
            })
        assert result["passed"] is False
        assert result["status"] == "not_registered"

    def test_boto3_not_available_returns_skipped(self):
        modules_backup = sys.modules.pop("boto3", None)
        try:
            result = _check_ssm_connectivity({
                "aws_instance_id": "i-abc",
                "region": "us-east-1",
            })
        finally:
            if modules_backup is not None:
                sys.modules["boto3"] = modules_backup
        assert result["passed"] is True
        assert result["status"] == "skipped"

    def test_boto3_exception_returns_error(self):
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.side_effect = Exception("SSM error")
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ssm
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_ssm_connectivity({
                "aws_instance_id": "i-abc",
                "region": "us-east-1",
            })
        assert result["passed"] is False
        assert result["status"] == "error"

    def test_detail_contains_ping_status(self):
        mock_ssm = MagicMock()
        mock_ssm.describe_instance_information.return_value = {
            "InstanceInformationList": [
                {"PingStatus": "Online", "AgentVersion": "3.3.0"}
            ]
        }
        boto3_mod = _make_boto3_mock()
        boto3_mod.client.return_value = mock_ssm
        with patch.dict(sys.modules, {"boto3": boto3_mod}):
            result = _check_ssm_connectivity({
                "aws_instance_id": "i-abc",
                "region": "us-east-1",
            })
        assert "ping_status=Online" in result["detail"]
        assert "agent_version=3.3.0" in result["detail"]


# ---------------------------------------------------------------------------
# _check_puppet_enrollment
# ---------------------------------------------------------------------------


class TestCheckPuppetEnrollment:
    def test_no_certname_and_no_server_name_returns_skipped(self):
        result = _check_puppet_enrollment({})
        assert result["passed"] is False
        assert result["status"] == "skipped"

    def test_puppet_service_none_returns_skipped(self):
        """When PuppetEnterpriseServiceSync is None (import failed), skip."""
        import app.tasks.validation as val_mod
        original = val_mod.PuppetEnterpriseServiceSync
        val_mod.PuppetEnterpriseServiceSync = None
        try:
            result = _check_puppet_enrollment({"puppet_certname": "mynode.corp.com"})
        finally:
            val_mod.PuppetEnterpriseServiceSync = original
        assert result["passed"] is True
        assert result["status"] == "skipped"

    def test_node_found_with_catalog_passes(self):
        mock_puppet = MagicMock()
        mock_puppet.get_node_status.return_value = {
            "latest_report_status": "changed",
            "catalog_timestamp": "2024-01-01T00:00:00Z",
        }
        mock_puppet_class = MagicMock(return_value=mock_puppet)

        import app.tasks.validation as val_mod
        original = val_mod.PuppetEnterpriseServiceSync
        val_mod.PuppetEnterpriseServiceSync = mock_puppet_class
        try:
            result = _check_puppet_enrollment({"puppet_certname": "mynode.corp.com"})
        finally:
            val_mod.PuppetEnterpriseServiceSync = original

        assert result["passed"] is True
        assert result["status"] == "changed"

    def test_node_not_found_returns_not_found(self):
        mock_puppet = MagicMock()
        mock_puppet.get_node_status.return_value = None
        mock_puppet_class = MagicMock(return_value=mock_puppet)

        import app.tasks.validation as val_mod
        original = val_mod.PuppetEnterpriseServiceSync
        val_mod.PuppetEnterpriseServiceSync = mock_puppet_class
        try:
            result = _check_puppet_enrollment({"puppet_certname": "missing.corp.com"})
        finally:
            val_mod.PuppetEnterpriseServiceSync = original

        assert result["passed"] is False
        assert result["status"] == "not_found"

    def test_node_found_without_catalog_timestamp_fails(self):
        mock_puppet = MagicMock()
        mock_puppet.get_node_status.return_value = {
            "latest_report_status": "failed",
            "catalog_timestamp": None,
        }
        mock_puppet_class = MagicMock(return_value=mock_puppet)

        import app.tasks.validation as val_mod
        original = val_mod.PuppetEnterpriseServiceSync
        val_mod.PuppetEnterpriseServiceSync = mock_puppet_class
        try:
            result = _check_puppet_enrollment({"puppet_certname": "mynode.corp.com"})
        finally:
            val_mod.PuppetEnterpriseServiceSync = original

        assert result["passed"] is False

    def test_puppet_exception_returns_error(self):
        mock_puppet = MagicMock()
        mock_puppet.get_node_status.side_effect = Exception("PE API error")
        mock_puppet_class = MagicMock(return_value=mock_puppet)

        import app.tasks.validation as val_mod
        original = val_mod.PuppetEnterpriseServiceSync
        val_mod.PuppetEnterpriseServiceSync = mock_puppet_class
        try:
            result = _check_puppet_enrollment({"puppet_certname": "mynode.corp.com"})
        finally:
            val_mod.PuppetEnterpriseServiceSync = original

        assert result["passed"] is False
        assert result["status"] == "error"
        assert "PE API error" in result["detail"]

    def test_puppet_service_close_called(self):
        mock_puppet = MagicMock()
        mock_puppet.get_node_status.return_value = {
            "latest_report_status": "unchanged",
            "catalog_timestamp": "2024-01-01T00:00:00Z",
        }
        mock_puppet_class = MagicMock(return_value=mock_puppet)

        import app.tasks.validation as val_mod
        original = val_mod.PuppetEnterpriseServiceSync
        val_mod.PuppetEnterpriseServiceSync = mock_puppet_class
        try:
            _check_puppet_enrollment({"puppet_certname": "mynode.corp.com"})
        finally:
            val_mod.PuppetEnterpriseServiceSync = original

        mock_puppet.close.assert_called_once()
