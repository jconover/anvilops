"""Unit tests for the RegionService.

Tests both static fallback paths and boto3 live-discovery paths.
All boto3 calls are mocked -- no real AWS credentials required.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.regions import (
    _STATIC_AZS,
    _STATIC_SUBNETS,
    _STATIC_VPCS,
    SUPPORTED_REGIONS,
    RegionService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service() -> RegionService:
    return RegionService()


# ---------------------------------------------------------------------------
# SUPPORTED_REGIONS constant
# ---------------------------------------------------------------------------


class TestSupportedRegions:
    def test_us_east_1_present(self):
        assert "us-east-1" in SUPPORTED_REGIONS

    def test_us_west_2_present(self):
        assert "us-west-2" in SUPPORTED_REGIONS

    def test_regions_have_required_keys(self):
        for region, meta in SUPPORTED_REGIONS.items():
            assert "name" in meta, f"Missing 'name' for {region}"
            assert "short_name" in meta, f"Missing 'short_name' for {region}"
            assert "enabled" in meta, f"Missing 'enabled' for {region}"
            assert "default_azs" in meta, f"Missing 'default_azs' for {region}"

    def test_all_regions_enabled(self):
        for region, meta in SUPPORTED_REGIONS.items():
            assert meta["enabled"] is True, f"{region} should be enabled"


# ---------------------------------------------------------------------------
# validate_region
# ---------------------------------------------------------------------------


class TestValidateRegion:
    def test_us_east_1_is_valid(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            assert service.validate_region("us-east-1") is True

    def test_us_west_2_is_valid(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            assert service.validate_region("us-west-2") is True

    def test_unsupported_region_is_invalid(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            assert service.validate_region("eu-west-1") is False

    def test_region_not_in_allowed_list_is_invalid(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1"]  # us-west-2 excluded
            assert service.validate_region("us-west-2") is False

    def test_empty_string_is_invalid(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            assert service.validate_region("") is False


# ---------------------------------------------------------------------------
# get_regions
# ---------------------------------------------------------------------------


class TestGetRegions:
    def test_returns_list_of_region_dicts(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            regions = service.get_regions()

        assert isinstance(regions, list)
        assert len(regions) >= 1

    def test_region_dict_has_required_keys(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1"]
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            regions = service.get_regions()

        assert len(regions) == 1
        r = regions[0]
        assert r["region"] == "us-east-1"
        assert "name" in r
        assert "short_name" in r
        assert "enabled" in r
        assert "is_default" in r

    def test_default_region_marked_correctly(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            regions = service.get_regions()

        region_map = {r["region"]: r for r in regions}
        assert region_map["us-east-1"]["is_default"] is True
        assert region_map["us-west-2"]["is_default"] is False

    def test_excludes_regions_not_in_allowed_list(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1"]
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            regions = service.get_regions()

        region_codes = [r["region"] for r in regions]
        assert "us-west-2" not in region_codes

    def test_empty_allowed_regions_returns_empty_list(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = []
            mock_settings.AWS_DEFAULT_REGION = "us-east-1"
            regions = service.get_regions()

        assert regions == []


# ---------------------------------------------------------------------------
# get_vpcs — static fallback path
# ---------------------------------------------------------------------------


class TestGetVpcsStaticFallback:
    def _patch_settings_and_raise_boto3(self, service, region):
        """Helper: make boto3 unavailable so static fallback is used."""
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.object(service, "_discover_vpcs_boto3", side_effect=ImportError("no boto3")):
                return service.get_vpcs(region)

    def test_us_east_1_returns_static_vpcs(self, service: RegionService):
        vpcs = self._patch_settings_and_raise_boto3(service, "us-east-1")
        assert len(vpcs) == len(_STATIC_VPCS["us-east-1"])

    def test_us_west_2_returns_static_vpcs(self, service: RegionService):
        vpcs = self._patch_settings_and_raise_boto3(service, "us-west-2")
        assert len(vpcs) == len(_STATIC_VPCS["us-west-2"])

    def test_vpc_dicts_have_required_keys(self, service: RegionService):
        vpcs = self._patch_settings_and_raise_boto3(service, "us-east-1")
        for vpc in vpcs:
            assert "vpc_id" in vpc
            assert "name" in vpc
            assert "cidr_block" in vpc
            assert "is_default" in vpc
            assert "state" in vpc

    def test_unsupported_region_raises_value_error(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1"]
            with pytest.raises(ValueError, match="not supported"):
                service.get_vpcs("eu-central-1")


# ---------------------------------------------------------------------------
# get_vpcs — boto3 live path
# ---------------------------------------------------------------------------


class TestGetVpcsBoto3:
    def test_returns_vpcs_from_boto3_describe(self, service: RegionService):
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpcs.return_value = {
            "Vpcs": [
                {
                    "VpcId": "vpc-live01",
                    "CidrBlock": "10.99.0.0/16",
                    "IsDefault": False,
                    "State": "available",
                    "Tags": [{"Key": "Name", "Value": "live-vpc"}],
                }
            ]
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_ec2

        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                vpcs = service.get_vpcs("us-east-1")

        assert len(vpcs) == 1
        assert vpcs[0]["vpc_id"] == "vpc-live01"
        assert vpcs[0]["name"] == "live-vpc"
        assert vpcs[0]["is_default"] is False

    def test_vpc_without_name_tag_returns_empty_name(self, service: RegionService):
        mock_ec2 = MagicMock()
        mock_ec2.describe_vpcs.return_value = {
            "Vpcs": [
                {
                    "VpcId": "vpc-notag",
                    "CidrBlock": "10.0.0.0/16",
                    "IsDefault": True,
                    "State": "available",
                    "Tags": [],
                }
            ]
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_ec2

        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                vpcs = service.get_vpcs("us-east-1")

        assert vpcs[0]["name"] == ""


# ---------------------------------------------------------------------------
# get_subnets — static fallback path
# ---------------------------------------------------------------------------


class TestGetSubnetsStaticFallback:
    def test_returns_subnets_for_known_vpc(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.object(
                service, "_discover_subnets_boto3", side_effect=ImportError("no boto3")
            ):
                subnets = service.get_subnets("us-east-1", "vpc-0a1b2c3d4e5f00001")

        assert len(subnets) > 0

    def test_returns_empty_for_unknown_vpc(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.object(
                service, "_discover_subnets_boto3", side_effect=ImportError("no boto3")
            ):
                subnets = service.get_subnets("us-east-1", "vpc-nonexistent")

        assert subnets == []

    def test_subnet_dicts_have_required_keys(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.object(
                service, "_discover_subnets_boto3", side_effect=ImportError("no boto3")
            ):
                subnets = service.get_subnets("us-east-1", "vpc-0a1b2c3d4e5f00001")

        for s in subnets:
            assert "subnet_id" in s
            assert "name" in s
            assert "cidr_block" in s
            assert "availability_zone" in s
            assert "available_ips" in s
            assert "is_public" in s
            assert "state" in s

    def test_unsupported_region_raises_value_error(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1"]
            with pytest.raises(ValueError, match="not supported"):
                service.get_subnets("ap-southeast-1", "vpc-xxx")


# ---------------------------------------------------------------------------
# get_availability_zones — static fallback path
# ---------------------------------------------------------------------------


class TestGetAvailabilityZones:
    def test_returns_azs_for_us_east_1(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.object(
                service, "_discover_azs_boto3", side_effect=ImportError("no boto3")
            ):
                azs = service.get_availability_zones("us-east-1")

        assert len(azs) == len(_STATIC_AZS["us-east-1"])

    def test_az_dicts_have_required_keys(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.object(
                service, "_discover_azs_boto3", side_effect=ImportError("no boto3")
            ):
                azs = service.get_availability_zones("us-east-1")

        for az in azs:
            assert "zone_name" in az
            assert "zone_id" in az
            assert "state" in az
            assert "zone_type" in az

    def test_unsupported_region_raises_value_error(self, service: RegionService):
        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1"]
            with pytest.raises(ValueError, match="not supported"):
                service.get_availability_zones("ca-central-1")

    def test_boto3_discovery_path(self, service: RegionService):
        mock_ec2 = MagicMock()
        mock_ec2.describe_availability_zones.return_value = {
            "AvailabilityZones": [
                {
                    "ZoneName": "us-east-1a",
                    "ZoneId": "use1-az1",
                    "State": "available",
                    "ZoneType": "availability-zone",
                }
            ]
        }
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_ec2

        with patch("app.services.regions.settings") as mock_settings:
            mock_settings.ALLOWED_REGIONS = ["us-east-1", "us-west-2"]
            with patch.dict("sys.modules", {"boto3": mock_boto3}):
                azs = service.get_availability_zones("us-east-1")

        assert len(azs) == 1
        assert azs[0]["zone_name"] == "us-east-1a"


# ---------------------------------------------------------------------------
# Static data consistency checks
# ---------------------------------------------------------------------------


class TestStaticDataConsistency:
    def test_static_vpcs_keys_match_supported_regions(self):
        for region in _STATIC_VPCS:
            assert region in SUPPORTED_REGIONS

    def test_static_subnets_keys_match_supported_regions(self):
        for region in _STATIC_SUBNETS:
            assert region in SUPPORTED_REGIONS

    def test_static_azs_keys_match_supported_regions(self):
        for region in _STATIC_AZS:
            assert region in SUPPORTED_REGIONS

    def test_us_east_1_has_three_vpcs(self):
        assert len(_STATIC_VPCS["us-east-1"]) == 3

    def test_us_west_2_has_three_vpcs(self):
        assert len(_STATIC_VPCS["us-west-2"]) == 3

    def test_us_east_1_has_three_azs(self):
        assert len(_STATIC_AZS["us-east-1"]) == 3

    def test_us_west_2_has_three_azs(self):
        assert len(_STATIC_AZS["us-west-2"]) == 3
