"""Multi-region Terraform workspace management.

Handles region-specific Terraform configurations, provider aliases,
and state management for multi-region deployments.  Each region gets
its own S3 state bucket and DynamoDB lock table to ensure complete
isolation between regions.
"""

import logging
from typing import Any

from app.services.regions import SUPPORTED_REGIONS, RegionService

logger = logging.getLogger(__name__)


# S3 state bucket and DynamoDB lock table naming convention per region.
# These are the buckets/tables that must be pre-created by the bootstrap
# Terraform configuration (see terraform/bootstrap/).
_STATE_BUCKET_TEMPLATE = "anvilops-tfstate-{region}"
_LOCK_TABLE_TEMPLATE = "anvilops-tflock-{region}"


class MultiRegionManager:
    """Coordinate Terraform operations across multiple AWS regions.

    Provides region-specific provider configuration, S3 backend
    configuration, and cross-region resource validation.  Used by
    the Celery task layer to configure Terraform before running
    init/plan/apply.
    """

    def __init__(self) -> None:
        self._region_service = RegionService()

    def get_region_config(self, region: str) -> dict[str, Any]:
        """Return region-specific Terraform provider configuration.

        Builds the ``provider "aws"`` block attributes for the given
        region including any required provider-level tags.

        Args:
            region: AWS region identifier (e.g. ``us-east-1``).

        Returns:
            Dictionary suitable for writing into a Terraform provider
            block or passing as CLI ``-var`` arguments::

                {
                    "region": "us-east-1",
                    "region_name": "US East (N. Virginia)",
                    "provider_alias": "aws.us_east_1",
                    "default_tags": {...},
                    "allowed_account_ids": [...],
                }

        Raises:
            ValueError: If the region is not supported/enabled.
        """
        if not self._region_service.validate_region(region):
            raise ValueError(
                f"Region '{region}' is not supported or not enabled. "
                f"Supported: {', '.join(sorted(SUPPORTED_REGIONS))}"
            )

        meta = SUPPORTED_REGIONS[region]
        # Terraform provider aliases cannot contain hyphens
        alias = f"aws.{region.replace('-', '_')}"

        return {
            "region": region,
            "region_name": meta["name"],
            "short_name": meta["short_name"],
            "provider_alias": alias,
            "default_tags": {
                "ManagedBy": "anvilops",
                "Platform": "anvilops",
                "Region": region,
            },
            "allowed_account_ids": [],  # populated from env/secrets in production
        }

    def get_backend_config(
        self, region: str, workspace: str
    ) -> dict[str, Any]:
        """Return S3 backend configuration for the region's state bucket.

        Each region has its own S3 bucket and DynamoDB lock table so
        that failures in one region's state management cannot affect
        another region.

        Args:
            region: AWS region identifier.
            workspace: Terraform workspace name (typically the server
                request ID or server name).

        Returns:
            Dictionary of S3 backend configuration values::

                {
                    "bucket": "anvilops-tfstate-us-east-1",
                    "key": "servers/<workspace>/terraform.tfstate",
                    "region": "us-east-1",
                    "dynamodb_table": "anvilops-tflock-us-east-1",
                    "encrypt": True,
                    "workspace_key_prefix": "servers",
                }

        Raises:
            ValueError: If the region is not supported/enabled.
        """
        if not self._region_service.validate_region(region):
            raise ValueError(
                f"Region '{region}' is not supported or not enabled. "
                f"Supported: {', '.join(sorted(SUPPORTED_REGIONS))}"
            )

        bucket = _STATE_BUCKET_TEMPLATE.format(region=region)
        lock_table = _LOCK_TABLE_TEMPLATE.format(region=region)

        return {
            "bucket": bucket,
            "key": f"servers/{workspace}/terraform.tfstate",
            "region": region,
            "dynamodb_table": lock_table,
            "encrypt": True,
            "workspace_key_prefix": "servers",
        }

    def validate_cross_region_resources(
        self, region: str, vpc_id: str, subnet_id: str
    ) -> dict[str, Any]:
        """Validate that VPC and subnet exist in the specified region.

        Performs a best-effort check that the user-selected VPC and
        subnet actually exist in the target region.  This catches
        common mistakes where a user picks a VPC from one region but
        targets a different region for deployment.

        Args:
            region: AWS region identifier.
            vpc_id: VPC ID to validate.
            subnet_id: Subnet ID to validate.

        Returns:
            Dictionary with validation results::

                {
                    "valid": True/False,
                    "region": "us-east-1",
                    "vpc_id": "vpc-...",
                    "subnet_id": "subnet-...",
                    "vpc_found": True/False,
                    "subnet_found": True/False,
                    "subnet_in_vpc": True/False,
                    "errors": ["..."],
                }

        Raises:
            ValueError: If the region is not supported/enabled.
        """
        if not self._region_service.validate_region(region):
            raise ValueError(
                f"Region '{region}' is not supported or not enabled. "
                f"Supported: {', '.join(sorted(SUPPORTED_REGIONS))}"
            )

        errors: list[str] = []
        vpc_found = False
        subnet_found = False
        subnet_in_vpc = False

        # Check VPC exists in region
        vpcs = self._region_service.get_vpcs(region)
        for vpc in vpcs:
            if vpc["vpc_id"] == vpc_id:
                vpc_found = True
                break

        if not vpc_found:
            errors.append(
                f"VPC '{vpc_id}' not found in region '{region}'. "
                f"Ensure the VPC exists and you have selected the correct region."
            )

        # Check subnet exists in the VPC
        if vpc_found:
            subnets = self._region_service.get_subnets(region, vpc_id)
            for subnet in subnets:
                if subnet["subnet_id"] == subnet_id:
                    subnet_found = True
                    subnet_in_vpc = True
                    break

            if not subnet_found:
                # The subnet may exist in a different VPC in the same region.
                # Check all VPCs to give a helpful error message.
                for vpc in vpcs:
                    if vpc["vpc_id"] == vpc_id:
                        continue
                    other_subnets = self._region_service.get_subnets(
                        region, vpc["vpc_id"]
                    )
                    for s in other_subnets:
                        if s["subnet_id"] == subnet_id:
                            subnet_found = True
                            errors.append(
                                f"Subnet '{subnet_id}' exists in VPC "
                                f"'{vpc['vpc_id']}', not in the selected "
                                f"VPC '{vpc_id}'."
                            )
                            break
                    if subnet_found:
                        break

                if not subnet_found:
                    errors.append(
                        f"Subnet '{subnet_id}' not found in region '{region}'."
                    )

        is_valid = vpc_found and subnet_found and subnet_in_vpc

        if is_valid:
            logger.info(
                "Cross-region validation passed: region=%s vpc=%s subnet=%s",
                region,
                vpc_id,
                subnet_id,
            )
        else:
            logger.warning(
                "Cross-region validation failed: region=%s vpc=%s subnet=%s errors=%s",
                region,
                vpc_id,
                subnet_id,
                errors,
            )

        return {
            "valid": is_valid,
            "region": region,
            "vpc_id": vpc_id,
            "subnet_id": subnet_id,
            "vpc_found": vpc_found,
            "subnet_found": subnet_found,
            "subnet_in_vpc": subnet_in_vpc,
            "errors": errors,
        }

    def get_all_region_configs(self) -> dict[str, dict[str, Any]]:
        """Return provider configuration for every enabled region.

        Convenience method for generating multi-provider Terraform
        configurations that need a provider alias per region.

        Returns:
            Dictionary mapping region code to its provider configuration.
        """
        configs: dict[str, dict[str, Any]] = {}
        for region_code in SUPPORTED_REGIONS:
            if self._region_service.validate_region(region_code):
                configs[region_code] = self.get_region_config(region_code)
        return configs

    def generate_backend_init_args(
        self, region: str, workspace: str
    ) -> list[str]:
        """Generate CLI arguments for ``terraform init -backend-config``.

        Produces a list of ``-backend-config=key=value`` arguments
        suitable for passing directly to a ``terraform init`` subprocess
        call.

        Args:
            region: AWS region identifier.
            workspace: Terraform workspace name.

        Returns:
            List of CLI argument strings.
        """
        backend_cfg = self.get_backend_config(region, workspace)
        args: list[str] = []
        for key, value in backend_cfg.items():
            if isinstance(value, bool):
                args.append(f"-backend-config={key}={str(value).lower()}")
            else:
                args.append(f"-backend-config={key}={value}")
        return args
