"""Unit tests for MultiRegionManager.

All region validation and VPC/subnet discovery calls are mocked
so no AWS credentials are needed.
"""

from unittest.mock import MagicMock

import pytest

from app.services.multi_region import (
    _LOCK_TABLE_TEMPLATE,
    _STATE_BUCKET_TEMPLATE,
    MultiRegionManager,
)
from app.services.regions import RegionService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_region_service() -> MagicMock:
    svc = MagicMock(spec=RegionService)
    svc.validate_region.side_effect = lambda r: r in ("us-east-1", "us-west-2")
    return svc


@pytest.fixture
def manager(mock_region_service: MagicMock) -> MultiRegionManager:
    mgr = MultiRegionManager()
    mgr._region_service = mock_region_service
    return mgr


# ---------------------------------------------------------------------------
# get_region_config
# ---------------------------------------------------------------------------


class TestGetRegionConfig:
    def test_returns_config_for_us_east_1(self, manager: MultiRegionManager):
        cfg = manager.get_region_config("us-east-1")

        assert cfg["region"] == "us-east-1"
        assert cfg["region_name"] == "US East (N. Virginia)"
        assert cfg["short_name"] == "Virginia"
        assert cfg["provider_alias"] == "aws.us_east_1"

    def test_returns_config_for_us_west_2(self, manager: MultiRegionManager):
        cfg = manager.get_region_config("us-west-2")

        assert cfg["region"] == "us-west-2"
        assert cfg["provider_alias"] == "aws.us_west_2"

    def test_provider_alias_replaces_hyphens_with_underscores(
        self, manager: MultiRegionManager
    ):
        cfg = manager.get_region_config("us-east-1")
        assert "-" not in cfg["provider_alias"]

    def test_default_tags_present(self, manager: MultiRegionManager):
        cfg = manager.get_region_config("us-east-1")
        tags = cfg["default_tags"]
        assert tags["ManagedBy"] == "anvilops"
        assert tags["Platform"] == "anvilops"
        assert tags["Region"] == "us-east-1"

    def test_allowed_account_ids_is_list(self, manager: MultiRegionManager):
        cfg = manager.get_region_config("us-east-1")
        assert isinstance(cfg["allowed_account_ids"], list)

    def test_unsupported_region_raises_value_error(self, manager: MultiRegionManager):
        with pytest.raises(ValueError, match="not supported"):
            manager.get_region_config("eu-central-1")


# ---------------------------------------------------------------------------
# get_backend_config
# ---------------------------------------------------------------------------


class TestGetBackendConfig:
    def test_returns_correct_bucket_name(self, manager: MultiRegionManager):
        cfg = manager.get_backend_config("us-east-1", "my-workspace")
        assert cfg["bucket"] == "anvilops-tfstate-us-east-1"

    def test_returns_correct_dynamodb_table(self, manager: MultiRegionManager):
        cfg = manager.get_backend_config("us-east-1", "my-workspace")
        assert cfg["dynamodb_table"] == "anvilops-tflock-us-east-1"

    def test_state_key_includes_workspace(self, manager: MultiRegionManager):
        cfg = manager.get_backend_config("us-east-1", "srv-request-abc123")
        assert "srv-request-abc123" in cfg["key"]

    def test_encryption_is_enabled(self, manager: MultiRegionManager):
        cfg = manager.get_backend_config("us-east-1", "ws")
        assert cfg["encrypt"] is True

    def test_region_field_matches_requested_region(self, manager: MultiRegionManager):
        cfg = manager.get_backend_config("us-west-2", "ws")
        assert cfg["region"] == "us-west-2"

    def test_workspace_key_prefix_is_servers(self, manager: MultiRegionManager):
        cfg = manager.get_backend_config("us-east-1", "ws")
        assert cfg["workspace_key_prefix"] == "servers"

    def test_us_west_2_bucket_name(self, manager: MultiRegionManager):
        cfg = manager.get_backend_config("us-west-2", "ws")
        assert cfg["bucket"] == "anvilops-tfstate-us-west-2"

    def test_unsupported_region_raises_value_error(self, manager: MultiRegionManager):
        with pytest.raises(ValueError, match="not supported"):
            manager.get_backend_config("ap-southeast-1", "ws")


# ---------------------------------------------------------------------------
# generate_backend_init_args
# ---------------------------------------------------------------------------


class TestGenerateBackendInitArgs:
    def test_returns_list_of_strings(self, manager: MultiRegionManager):
        args = manager.generate_backend_init_args("us-east-1", "my-ws")
        assert isinstance(args, list)
        assert all(isinstance(a, str) for a in args)

    def test_args_use_backend_config_prefix(self, manager: MultiRegionManager):
        args = manager.generate_backend_init_args("us-east-1", "my-ws")
        assert all(a.startswith("-backend-config=") for a in args)

    def test_bucket_arg_present(self, manager: MultiRegionManager):
        args = manager.generate_backend_init_args("us-east-1", "my-ws")
        bucket_args = [a for a in args if "bucket=" in a]
        assert len(bucket_args) == 1
        assert "anvilops-tfstate-us-east-1" in bucket_args[0]

    def test_encrypt_is_lowercased_bool(self, manager: MultiRegionManager):
        args = manager.generate_backend_init_args("us-east-1", "my-ws")
        encrypt_args = [a for a in args if "encrypt=" in a]
        assert len(encrypt_args) == 1
        # bool True should be serialized as "true" not "True"
        assert "true" in encrypt_args[0]

    def test_key_arg_includes_workspace(self, manager: MultiRegionManager):
        args = manager.generate_backend_init_args("us-east-1", "srv-abc")
        key_args = [a for a in args if "key=" in a]
        assert len(key_args) == 1
        assert "srv-abc" in key_args[0]


# ---------------------------------------------------------------------------
# validate_cross_region_resources
# ---------------------------------------------------------------------------


class TestValidateCrossRegionResources:
    def _setup_vpcs_and_subnets(self, mock_region_service: MagicMock):
        """Configure mock to return static VPCs and subnets."""
        mock_region_service.get_vpcs.return_value = [
            {"vpc_id": "vpc-valid", "name": "prod", "cidr_block": "10.0.0.0/16"},
            {"vpc_id": "vpc-other", "name": "dev", "cidr_block": "10.1.0.0/16"},
        ]

        def get_subnets(region, vpc_id):
            if vpc_id == "vpc-valid":
                return [{"subnet_id": "subnet-valid", "name": "private-1a"}]
            if vpc_id == "vpc-other":
                return [{"subnet_id": "subnet-other-vpc", "name": "private-1b"}]
            return []

        mock_region_service.get_subnets.side_effect = get_subnets

    def test_valid_vpc_and_subnet_returns_valid_true(
        self, manager: MultiRegionManager, mock_region_service: MagicMock
    ):
        self._setup_vpcs_and_subnets(mock_region_service)
        result = manager.validate_cross_region_resources(
            "us-east-1", "vpc-valid", "subnet-valid"
        )
        assert result["valid"] is True
        assert result["vpc_found"] is True
        assert result["subnet_found"] is True
        assert result["subnet_in_vpc"] is True
        assert result["errors"] == []

    def test_missing_vpc_returns_valid_false(
        self, manager: MultiRegionManager, mock_region_service: MagicMock
    ):
        self._setup_vpcs_and_subnets(mock_region_service)
        result = manager.validate_cross_region_resources(
            "us-east-1", "vpc-nonexistent", "subnet-valid"
        )
        assert result["valid"] is False
        assert result["vpc_found"] is False
        assert len(result["errors"]) >= 1

    def test_subnet_in_wrong_vpc_reports_error(
        self, manager: MultiRegionManager, mock_region_service: MagicMock
    ):
        self._setup_vpcs_and_subnets(mock_region_service)
        # subnet-other-vpc lives in vpc-other, not vpc-valid
        result = manager.validate_cross_region_resources(
            "us-east-1", "vpc-valid", "subnet-other-vpc"
        )
        assert result["valid"] is False
        assert result["subnet_in_vpc"] is False
        assert any("vpc-other" in e for e in result["errors"])

    def test_subnet_not_found_anywhere_reports_error(
        self, manager: MultiRegionManager, mock_region_service: MagicMock
    ):
        self._setup_vpcs_and_subnets(mock_region_service)
        result = manager.validate_cross_region_resources(
            "us-east-1", "vpc-valid", "subnet-totally-missing"
        )
        assert result["valid"] is False
        assert result["subnet_found"] is False

    def test_result_contains_input_fields(
        self, manager: MultiRegionManager, mock_region_service: MagicMock
    ):
        self._setup_vpcs_and_subnets(mock_region_service)
        result = manager.validate_cross_region_resources(
            "us-east-1", "vpc-valid", "subnet-valid"
        )
        assert result["region"] == "us-east-1"
        assert result["vpc_id"] == "vpc-valid"
        assert result["subnet_id"] == "subnet-valid"

    def test_unsupported_region_raises_value_error(self, manager: MultiRegionManager):
        with pytest.raises(ValueError, match="not supported"):
            manager.validate_cross_region_resources(
                "ap-southeast-2", "vpc-x", "subnet-y"
            )


# ---------------------------------------------------------------------------
# get_all_region_configs
# ---------------------------------------------------------------------------


class TestGetAllRegionConfigs:
    def test_returns_configs_for_all_valid_regions(self, manager: MultiRegionManager):
        configs = manager.get_all_region_configs()
        assert "us-east-1" in configs
        assert "us-west-2" in configs

    def test_each_config_has_provider_alias(self, manager: MultiRegionManager):
        configs = manager.get_all_region_configs()
        for region, cfg in configs.items():
            assert "provider_alias" in cfg
            assert cfg["provider_alias"].startswith("aws.")

    def test_returns_empty_when_no_regions_valid(
        self, manager: MultiRegionManager, mock_region_service: MagicMock
    ):
        # Override validate_region to reject all regions
        mock_region_service.validate_region.side_effect = lambda r: False
        configs = manager.get_all_region_configs()
        assert configs == {}


# ---------------------------------------------------------------------------
# Naming template constants
# ---------------------------------------------------------------------------


class TestNamingTemplates:
    def test_state_bucket_template_format(self):
        result = _STATE_BUCKET_TEMPLATE.format(region="us-east-1")
        assert result == "anvilops-tfstate-us-east-1"

    def test_lock_table_template_format(self):
        result = _LOCK_TABLE_TEMPLATE.format(region="us-west-2")
        assert result == "anvilops-tflock-us-west-2"
