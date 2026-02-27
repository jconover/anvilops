"""Unit tests for the TerraformService.

All subprocess calls are patched so no real Terraform binary is required.
"""

import json
import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app.services.terraform import INSTANCE_SIZE_MAP, TerraformService


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tf(tmp_path):
    """Return a TerraformService pointed at a temporary directory."""
    env_dir = tmp_path / "environments" / "dev"
    env_dir.mkdir(parents=True)
    return TerraformService(work_dir=str(tmp_path), environment="dev")


def _make_completed_process(returncode: int, stdout: str = "", stderr: str = ""):
    proc = MagicMock(spec=subprocess.CompletedProcess)
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestTerraformServiceInit:
    def test_env_dir_set_correctly(self, tmp_path):
        env_dir = tmp_path / "environments" / "staging"
        env_dir.mkdir(parents=True)
        svc = TerraformService(str(tmp_path), "staging")
        assert svc.env_dir == str(env_dir)

    def test_missing_env_dir_logs_warning(self, tmp_path, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            TerraformService(str(tmp_path), "nonexistent")
        assert "does not exist" in caplog.text

    def test_work_dir_and_environment_stored(self, tmp_path):
        (tmp_path / "environments" / "prod").mkdir(parents=True)
        svc = TerraformService(str(tmp_path), "prod")
        assert svc.work_dir == str(tmp_path)
        assert svc.environment == "prod"


# ---------------------------------------------------------------------------
# INSTANCE_SIZE_MAP
# ---------------------------------------------------------------------------


class TestInstanceSizeMap:
    def test_small_maps_to_t3_medium(self):
        assert INSTANCE_SIZE_MAP["small"] == "t3.medium"

    def test_medium_maps_to_t3_xlarge(self):
        assert INSTANCE_SIZE_MAP["medium"] == "t3.xlarge"

    def test_large_maps_to_m5_2xlarge(self):
        assert INSTANCE_SIZE_MAP["large"] == "m5.2xlarge"

    def test_xl_maps_to_m5_4xlarge(self):
        assert INSTANCE_SIZE_MAP["xl"] == "m5.4xlarge"


# ---------------------------------------------------------------------------
# generate_tfvars
# ---------------------------------------------------------------------------


class TestGenerateTfvars:
    def test_basic_fields_written(self, tf):
        request = {
            "id": "abc123",
            "server_name": "TEST-WEB-01",
            "environment": "dev",
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
            "vpc_id": "vpc-111",
            "subnet_id": "subnet-222",
            "security_profile": "internal_only",
            "domain_join": False,
        }
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert 'server_name      = "TEST-WEB-01"' in content
        assert 'environment      = "dev"' in content
        assert 'instance_type    = "t3.medium"' in content
        assert 'os_type          = "amazon_linux_2023"' in content
        assert "is_windows       = false" in content
        assert 'region           = "us-east-1"' in content

    def test_windows_detected_correctly(self, tf):
        request = {
            "id": "win1",
            "server_name": "WIN-DB-01",
            "environment": "dev",
            "instance_size": "large",
            "os_type": "windows_2022",
        }
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert "is_windows       = true" in content
        assert 'instance_type    = "m5.2xlarge"' in content

    def test_unknown_instance_size_defaults_to_t3_medium(self, tf):
        request = {"id": "x1", "instance_size": "micro", "os_type": "amazon_linux_2023"}
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert 'instance_type    = "t3.medium"' in content

    def test_additional_storage_serialized_as_json(self, tf):
        volumes = [{"drive_letter": "D", "size_gb": 100, "volume_type": "gp3"}]
        request = {
            "id": "vol1",
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "additional_storage": volumes,
        }
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert "additional_volumes" in content
        assert json.dumps(volumes) in content

    def test_tags_written_as_hcl_block(self, tf):
        request = {
            "id": "tag1",
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "tags": {"env": "dev", "team": "ops"},
        }
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert "tags = {" in content
        assert 'env = "dev"' in content
        assert 'team = "ops"' in content

    def test_puppet_role_written(self, tf):
        request = {
            "id": "pup1",
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "puppet_role": "web_server",
        }
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert 'puppet_role = "web_server"' in content

    def test_software_packages_written(self, tf):
        request = {
            "id": "sw1",
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "software_packages": ["nginx", "git"],
        }
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert 'software_packages = ["nginx", "git"]' in content

    def test_tags_not_written_if_not_dict(self, tf):
        """Non-dict tags value should be silently ignored."""
        request = {
            "id": "bad-tags",
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "tags": "not-a-dict",
        }
        path = tf.generate_tfvars(request)
        content = open(path).read()
        assert "tags = {" not in content

    def test_file_created_in_env_dir(self, tf):
        request = {"id": "filetest", "instance_size": "small", "os_type": "amazon_linux_2023"}
        path = tf.generate_tfvars(request)
        assert os.path.isfile(path)
        assert "server-filetest.tfvars" in path


# ---------------------------------------------------------------------------
# _run_command
# ---------------------------------------------------------------------------


class TestRunCommand:
    def test_returns_returncode_and_combined_output(self, tf):
        proc = _make_completed_process(0, stdout="hello\n", stderr="warn\n")
        with patch("subprocess.run", return_value=proc):
            code, output = tf._run_command(["terraform", "version"])
        assert code == 0
        assert "hello" in output
        assert "warn" in output

    def test_nonzero_returncode_propagated(self, tf):
        proc = _make_completed_process(1, stderr="Error: something went wrong")
        with patch("subprocess.run", return_value=proc):
            code, output = tf._run_command(["terraform", "plan"])
        assert code == 1
        assert "something went wrong" in output

    def test_timeout_returns_1_and_message(self, tf):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 600)):
            code, output = tf._run_command(["terraform", "apply"])
        assert code == 1
        assert "timed out" in output.lower()

    def test_file_not_found_returns_1(self, tf):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            code, output = tf._run_command(["terraform", "init"])
        assert code == 1
        assert "not found" in output.lower()

    def test_generic_exception_returns_1(self, tf):
        with patch("subprocess.run", side_effect=OSError("disk error")):
            code, output = tf._run_command(["terraform", "plan"])
        assert code == 1

    def test_tf_in_automation_env_var_set(self, tf):
        """TF_IN_AUTOMATION=1 must be passed to subprocess."""
        proc = _make_completed_process(0)
        with patch("subprocess.run", return_value=proc) as mock_run:
            tf._run_command(["terraform", "version"])
        _, kwargs = mock_run.call_args
        assert kwargs["env"]["TF_IN_AUTOMATION"] == "1"


# ---------------------------------------------------------------------------
# init / plan / destroy — command construction
# ---------------------------------------------------------------------------


class TestCommandConstruction:
    def _patch_run(self, returncode=0, stdout="", stderr=""):
        proc = _make_completed_process(returncode, stdout, stderr)
        return patch("subprocess.run", return_value=proc)

    def test_init_calls_correct_subcommand(self, tf):
        with self._patch_run() as mock_run:
            tf.init()
        cmd = mock_run.call_args[0][0]
        assert "init" in cmd
        assert "-input=false" in cmd
        assert "-no-color" in cmd

    def test_plan_passes_var_file(self, tf):
        with self._patch_run() as mock_run:
            tf.plan("/tmp/server-x.tfvars")
        cmd = mock_run.call_args[0][0]
        assert "plan" in cmd
        assert "-var-file=/tmp/server-x.tfvars" in cmd

    def test_apply_passes_var_file_and_auto_approve(self, tf):
        outputs_json = json.dumps({"instance_id": {"value": "i-abc"}})
        responses = [
            _make_completed_process(0, stdout="Apply complete!"),
            _make_completed_process(0, stdout=outputs_json),
        ]
        with patch("subprocess.run", side_effect=responses) as mock_run:
            code, output, outputs = tf.apply("/tmp/server-x.tfvars")
        first_cmd = mock_run.call_args_list[0][0][0]
        assert "apply" in first_cmd
        assert "-auto-approve" in first_cmd
        assert "-var-file=/tmp/server-x.tfvars" in first_cmd
        assert code == 0

    def test_destroy_passes_var_file_and_auto_approve(self, tf):
        with self._patch_run() as mock_run:
            tf.destroy("/tmp/server-x.tfvars")
        cmd = mock_run.call_args[0][0]
        assert "destroy" in cmd
        assert "-auto-approve" in cmd


# ---------------------------------------------------------------------------
# apply — output parsing
# ---------------------------------------------------------------------------


class TestApplyOutputParsing:
    def test_apply_success_returns_parsed_outputs(self, tf):
        tf_outputs = {"instance_id": {"value": "i-0abc123"}, "private_ip": {"value": "10.0.0.5"}}
        responses = [
            _make_completed_process(0, stdout="Apply complete!"),
            _make_completed_process(0, stdout=json.dumps(tf_outputs)),
        ]
        with patch("subprocess.run", side_effect=responses):
            code, output, outputs = tf.apply("/tmp/vars.tfvars")
        assert code == 0
        assert outputs["instance_id"] == "i-0abc123"
        assert outputs["private_ip"] == "10.0.0.5"

    def test_apply_failure_returns_empty_outputs(self, tf):
        with patch("subprocess.run", return_value=_make_completed_process(1, stderr="Error")):
            code, output, outputs = tf.apply("/tmp/vars.tfvars")
        assert code == 1
        assert outputs == {}

    def test_apply_get_outputs_failure_logs_warning(self, tf, caplog):
        import logging

        responses = [
            _make_completed_process(0, stdout="Apply complete!"),
            _make_completed_process(1, stderr="output command failed"),
        ]
        with patch("subprocess.run", side_effect=responses):
            with caplog.at_level(logging.WARNING):
                code, output, outputs = tf.apply("/tmp/vars.tfvars")
        assert outputs == {}
        assert "Failed to read terraform outputs" in caplog.text


# ---------------------------------------------------------------------------
# get_outputs
# ---------------------------------------------------------------------------


class TestGetOutputs:
    def test_parses_json_correctly(self, tf):
        raw = {"vpc_id": {"value": "vpc-abc"}, "region": {"value": "us-east-1"}}
        proc = _make_completed_process(0, stdout=json.dumps(raw))
        with patch("subprocess.run", return_value=proc):
            result = tf.get_outputs()
        assert result["vpc_id"] == "vpc-abc"
        assert result["region"] == "us-east-1"

    def test_raises_on_nonzero_exit(self, tf):
        proc = _make_completed_process(1, stderr="no outputs")
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(RuntimeError, match="terraform output failed"):
                tf.get_outputs()


# ---------------------------------------------------------------------------
# setup_workspace
# ---------------------------------------------------------------------------


class TestSetupWorkspace:
    def test_select_succeeds_no_create(self, tf):
        proc_ok = _make_completed_process(0)
        with patch("subprocess.run", return_value=proc_ok) as mock_run:
            tf.setup_workspace("my-workspace")
        # Only one call: select
        assert mock_run.call_count == 1
        cmd = mock_run.call_args[0][0]
        assert "select" in cmd
        assert "my-workspace" in cmd

    def test_select_fails_then_create_called(self, tf):
        proc_fail = _make_completed_process(1, stderr="no workspace")
        proc_ok = _make_completed_process(0)
        with patch("subprocess.run", side_effect=[proc_fail, proc_ok]) as mock_run:
            tf.setup_workspace("new-workspace")
        assert mock_run.call_count == 2
        new_cmd = mock_run.call_args_list[1][0][0]
        assert "new" in new_cmd
        assert "new-workspace" in new_cmd

    def test_create_fails_raises_runtime_error(self, tf):
        proc_fail = _make_completed_process(1, stderr="error")
        with patch("subprocess.run", return_value=proc_fail):
            with pytest.raises(RuntimeError, match="Failed to create workspace"):
                tf.setup_workspace("broken-workspace")
