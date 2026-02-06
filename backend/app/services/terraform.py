"""
Terraform service layer.

Encapsulates all interactions with the Terraform CLI: workspace management,
tfvars generation, init, plan, apply, destroy, and output parsing.
"""

import json
import logging
import os
import subprocess

from app.core.config import settings

logger = logging.getLogger(__name__)

INSTANCE_SIZE_MAP: dict[str, str] = {
    "small": "t3.medium",     # 2 vCPU / 4GB
    "medium": "t3.xlarge",    # 4 vCPU / 16GB
    "large": "m5.2xlarge",    # 8 vCPU / 32GB
    "xl": "m5.4xlarge",       # 16 vCPU / 64GB
}

DEFAULT_COMMAND_TIMEOUT = 600


class TerraformService:
    """Manages Terraform operations for a single environment."""

    def __init__(self, work_dir: str, environment: str) -> None:
        self.work_dir = work_dir
        self.environment = environment
        self.env_dir = os.path.join(work_dir, "environments", environment)
        self.terraform_bin = "terraform"

        if not os.path.isdir(self.env_dir):
            logger.warning("Terraform env dir does not exist: %s", self.env_dir)

    def setup_workspace(self, workspace_name: str) -> None:
        """Create (if needed) and select a Terraform workspace."""
        exit_code, output = self._run_command(
            [self.terraform_bin, "workspace", "select", workspace_name]
        )
        if exit_code != 0:
            logger.info("Creating terraform workspace: %s", workspace_name)
            exit_code, output = self._run_command(
                [self.terraform_bin, "workspace", "new", workspace_name]
            )
            if exit_code != 0:
                raise RuntimeError(
                    f"Failed to create workspace '{workspace_name}': {output}"
                )
        logger.info("Using terraform workspace: %s", workspace_name)

    def generate_tfvars(self, server_request: dict) -> str:
        """Convert a server request dict into a .tfvars file."""
        request_id = server_request.get("id", "unknown")
        var_file_path = os.path.join(self.env_dir, f"server-{request_id}.tfvars")

        instance_size = server_request.get("instance_size", "small").lower()
        instance_type = INSTANCE_SIZE_MAP.get(instance_size, "t3.medium")

        os_type = server_request.get("os_type", "amazon_linux_2023").lower()
        is_windows = "windows" in os_type

        tfvars_lines = [
            f'server_name      = "{server_request.get("server_name", "")}"',
            f'environment      = "{server_request.get("environment", "dev")}"',
            f'instance_type    = "{instance_type}"',
            f'os_type          = "{os_type}"',
            f'is_windows       = {str(is_windows).lower()}',
            f'region           = "{server_request.get("region", settings.AWS_DEFAULT_REGION)}"',
            f'vpc_id           = "{server_request.get("vpc_id", "")}"',
            f'subnet_id        = "{server_request.get("subnet_id", "")}"',
            f'security_profile = "{server_request.get("security_profile", "internal_only")}"',
            f'domain_join      = {str(server_request.get("domain_join", False)).lower()}',
        ]

        # Additional EBS volumes
        volumes = server_request.get("additional_storage")
        if volumes:
            tfvars_lines.append(f"additional_volumes = {json.dumps(volumes)}")

        # Tags
        tags = server_request.get("tags")
        if tags and isinstance(tags, dict):
            tag_block = "\n".join(f'    {k} = "{v}"' for k, v in tags.items())
            tfvars_lines.append(f"tags = {{\n{tag_block}\n}}")

        # Puppet role
        puppet_role = server_request.get("puppet_role")
        if puppet_role:
            tfvars_lines.append(f'puppet_role = "{puppet_role}"')

        # Software packages
        software = server_request.get("software_packages")
        if software and isinstance(software, list):
            pkgs = ", ".join(f'"{p}"' for p in software)
            tfvars_lines.append(f"software_packages = [{pkgs}]")

        tfvars_content = "\n".join(tfvars_lines) + "\n"

        os.makedirs(os.path.dirname(var_file_path), exist_ok=True)
        with open(var_file_path, "w", encoding="utf-8") as f:
            f.write(tfvars_content)

        logger.info("Generated tfvars file: %s", var_file_path)
        return var_file_path

    def init(self) -> tuple[int, str]:
        """Run terraform init."""
        logger.info("Running terraform init in %s", self.env_dir)
        return self._run_command(
            [self.terraform_bin, "init", "-input=false", "-no-color"]
        )

    def plan(self, var_file: str) -> tuple[int, str]:
        """Run terraform plan."""
        logger.info("Running terraform plan with %s", var_file)
        return self._run_command([
            self.terraform_bin, "plan",
            f"-var-file={var_file}", "-input=false", "-no-color",
        ])

    def apply(self, var_file: str) -> tuple[int, str, dict]:
        """Run terraform apply -auto-approve."""
        logger.info("Running terraform apply with %s", var_file)
        exit_code, output = self._run_command([
            self.terraform_bin, "apply", "-auto-approve",
            f"-var-file={var_file}", "-input=false", "-no-color",
        ])

        outputs = {}
        if exit_code == 0:
            try:
                outputs = self.get_outputs()
            except Exception as exc:
                logger.warning("Failed to read terraform outputs: %s", exc)

        return exit_code, output, outputs

    def destroy(self, var_file: str) -> tuple[int, str]:
        """Run terraform destroy -auto-approve."""
        logger.info("Running terraform destroy with %s", var_file)
        return self._run_command([
            self.terraform_bin, "destroy", "-auto-approve",
            f"-var-file={var_file}", "-input=false", "-no-color",
        ])

    def get_outputs(self) -> dict:
        """Run terraform output -json and parse results."""
        exit_code, output = self._run_command(
            [self.terraform_bin, "output", "-json", "-no-color"]
        )
        if exit_code != 0:
            raise RuntimeError(f"terraform output failed: {output}")

        raw = json.loads(output)
        return {k: v.get("value") for k, v in raw.items()}

    def _run_command(
        self, cmd: list[str], timeout: int = DEFAULT_COMMAND_TIMEOUT
    ) -> tuple[int, str]:
        """Execute a subprocess command and capture output."""
        logger.debug("Running: %s (cwd=%s)", " ".join(cmd), self.env_dir)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.env_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "TF_IN_AUTOMATION": "1"},
            )
            combined = result.stdout + result.stderr
            if result.returncode != 0:
                logger.warning(
                    "Command exited %d: %s\n%s",
                    result.returncode, " ".join(cmd), combined[-1000:],
                )
            return result.returncode, combined

        except subprocess.TimeoutExpired:
            msg = f"Command timed out after {timeout}s: {' '.join(cmd)}"
            logger.error(msg)
            return 1, msg

        except FileNotFoundError:
            msg = f"Terraform binary not found at '{self.terraform_bin}'."
            logger.error(msg)
            return 1, msg

        except Exception as exc:
            msg = f"Unexpected error running command: {exc}"
            logger.exception(msg)
            return 1, msg
