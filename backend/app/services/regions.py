"""Multi-region configuration and AWS network discovery for AnvilOps.

Manages region definitions, VPC/subnet lookups, and availability zone
data for the server builder wizard. Uses boto3 for real AWS discovery
with a static fallback for development.
"""

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


SUPPORTED_REGIONS: dict[str, dict[str, Any]] = {
    "us-east-1": {
        "name": "US East (N. Virginia)",
        "short_name": "Virginia",
        "enabled": True,
        "default_azs": ["us-east-1a", "us-east-1b", "us-east-1c"],
    },
    "us-west-2": {
        "name": "US West (Oregon)",
        "short_name": "Oregon",
        "enabled": True,
        "default_azs": ["us-west-2a", "us-west-2b", "us-west-2c"],
    },
}


# ---------------------------------------------------------------------------
# Static development data
# ---------------------------------------------------------------------------

_STATIC_VPCS: dict[str, list[dict[str, Any]]] = {
    "us-east-1": [
        {
            "vpc_id": "vpc-0a1b2c3d4e5f00001",
            "name": "anvilops-prod-east",
            "cidr_block": "10.0.0.0/16",
            "is_default": False,
            "state": "available",
        },
        {
            "vpc_id": "vpc-0a1b2c3d4e5f00002",
            "name": "anvilops-dev-east",
            "cidr_block": "10.1.0.0/16",
            "is_default": False,
            "state": "available",
        },
        {
            "vpc_id": "vpc-0a1b2c3d4e5f00003",
            "name": "default",
            "cidr_block": "172.31.0.0/16",
            "is_default": True,
            "state": "available",
        },
    ],
    "us-west-2": [
        {
            "vpc_id": "vpc-0f1e2d3c4b5a00001",
            "name": "anvilops-prod-west",
            "cidr_block": "10.10.0.0/16",
            "is_default": False,
            "state": "available",
        },
        {
            "vpc_id": "vpc-0f1e2d3c4b5a00002",
            "name": "anvilops-dev-west",
            "cidr_block": "10.11.0.0/16",
            "is_default": False,
            "state": "available",
        },
        {
            "vpc_id": "vpc-0f1e2d3c4b5a00003",
            "name": "default",
            "cidr_block": "172.31.0.0/16",
            "is_default": True,
            "state": "available",
        },
    ],
}

_STATIC_SUBNETS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "us-east-1": {
        "vpc-0a1b2c3d4e5f00001": [
            {
                "subnet_id": "subnet-0aaa0001",
                "name": "prod-east-public-1a",
                "cidr_block": "10.0.1.0/24",
                "availability_zone": "us-east-1a",
                "available_ips": 246,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0aaa0002",
                "name": "prod-east-private-1a",
                "cidr_block": "10.0.10.0/24",
                "availability_zone": "us-east-1a",
                "available_ips": 250,
                "is_public": False,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0aaa0003",
                "name": "prod-east-private-1b",
                "cidr_block": "10.0.11.0/24",
                "availability_zone": "us-east-1b",
                "available_ips": 248,
                "is_public": False,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0aaa0004",
                "name": "prod-east-private-1c",
                "cidr_block": "10.0.12.0/24",
                "availability_zone": "us-east-1c",
                "available_ips": 251,
                "is_public": False,
                "state": "available",
            },
        ],
        "vpc-0a1b2c3d4e5f00002": [
            {
                "subnet_id": "subnet-0bbb0001",
                "name": "dev-east-public-1a",
                "cidr_block": "10.1.1.0/24",
                "availability_zone": "us-east-1a",
                "available_ips": 240,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0bbb0002",
                "name": "dev-east-private-1a",
                "cidr_block": "10.1.10.0/24",
                "availability_zone": "us-east-1a",
                "available_ips": 252,
                "is_public": False,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0bbb0003",
                "name": "dev-east-private-1b",
                "cidr_block": "10.1.11.0/24",
                "availability_zone": "us-east-1b",
                "available_ips": 249,
                "is_public": False,
                "state": "available",
            },
        ],
        "vpc-0a1b2c3d4e5f00003": [
            {
                "subnet_id": "subnet-0ccc0001",
                "name": "default-1a",
                "cidr_block": "172.31.0.0/20",
                "availability_zone": "us-east-1a",
                "available_ips": 4089,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0ccc0002",
                "name": "default-1b",
                "cidr_block": "172.31.16.0/20",
                "availability_zone": "us-east-1b",
                "available_ips": 4090,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0ccc0003",
                "name": "default-1c",
                "cidr_block": "172.31.32.0/20",
                "availability_zone": "us-east-1c",
                "available_ips": 4091,
                "is_public": True,
                "state": "available",
            },
        ],
    },
    "us-west-2": {
        "vpc-0f1e2d3c4b5a00001": [
            {
                "subnet_id": "subnet-0ddd0001",
                "name": "prod-west-public-2a",
                "cidr_block": "10.10.1.0/24",
                "availability_zone": "us-west-2a",
                "available_ips": 245,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0ddd0002",
                "name": "prod-west-private-2a",
                "cidr_block": "10.10.10.0/24",
                "availability_zone": "us-west-2a",
                "available_ips": 250,
                "is_public": False,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0ddd0003",
                "name": "prod-west-private-2b",
                "cidr_block": "10.10.11.0/24",
                "availability_zone": "us-west-2b",
                "available_ips": 249,
                "is_public": False,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0ddd0004",
                "name": "prod-west-private-2c",
                "cidr_block": "10.10.12.0/24",
                "availability_zone": "us-west-2c",
                "available_ips": 252,
                "is_public": False,
                "state": "available",
            },
        ],
        "vpc-0f1e2d3c4b5a00002": [
            {
                "subnet_id": "subnet-0eee0001",
                "name": "dev-west-public-2a",
                "cidr_block": "10.11.1.0/24",
                "availability_zone": "us-west-2a",
                "available_ips": 243,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0eee0002",
                "name": "dev-west-private-2a",
                "cidr_block": "10.11.10.0/24",
                "availability_zone": "us-west-2a",
                "available_ips": 251,
                "is_public": False,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0eee0003",
                "name": "dev-west-private-2b",
                "cidr_block": "10.11.11.0/24",
                "availability_zone": "us-west-2b",
                "available_ips": 250,
                "is_public": False,
                "state": "available",
            },
        ],
        "vpc-0f1e2d3c4b5a00003": [
            {
                "subnet_id": "subnet-0fff0001",
                "name": "default-2a",
                "cidr_block": "172.31.0.0/20",
                "availability_zone": "us-west-2a",
                "available_ips": 4088,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0fff0002",
                "name": "default-2b",
                "cidr_block": "172.31.16.0/20",
                "availability_zone": "us-west-2b",
                "available_ips": 4090,
                "is_public": True,
                "state": "available",
            },
            {
                "subnet_id": "subnet-0fff0003",
                "name": "default-2c",
                "cidr_block": "172.31.32.0/20",
                "availability_zone": "us-west-2c",
                "available_ips": 4092,
                "is_public": True,
                "state": "available",
            },
        ],
    },
}

_STATIC_AZS: dict[str, list[dict[str, Any]]] = {
    "us-east-1": [
        {
            "zone_name": "us-east-1a",
            "zone_id": "use1-az1",
            "state": "available",
            "zone_type": "availability-zone",
        },
        {
            "zone_name": "us-east-1b",
            "zone_id": "use1-az2",
            "state": "available",
            "zone_type": "availability-zone",
        },
        {
            "zone_name": "us-east-1c",
            "zone_id": "use1-az4",
            "state": "available",
            "zone_type": "availability-zone",
        },
    ],
    "us-west-2": [
        {
            "zone_name": "us-west-2a",
            "zone_id": "usw2-az1",
            "state": "available",
            "zone_type": "availability-zone",
        },
        {
            "zone_name": "us-west-2b",
            "zone_id": "usw2-az2",
            "state": "available",
            "zone_type": "availability-zone",
        },
        {
            "zone_name": "us-west-2c",
            "zone_id": "usw2-az3",
            "state": "available",
            "zone_type": "availability-zone",
        },
    ],
}


class RegionService:
    """Discover VPCs, subnets, and AZs per region.

    Attempts live AWS discovery via boto3.  If credentials are not
    configured or boto3 is unavailable, the service gracefully falls
    back to static development data so the frontend wizard still
    functions without a real AWS account.
    """

    def get_regions(self) -> list[dict[str, Any]]:
        """Return list of supported regions with metadata.

        Only regions listed in ``SUPPORTED_REGIONS`` *and* present in the
        application's ``ALLOWED_REGIONS`` setting are returned.  Each
        entry includes the region code, display name, short name, and
        enabled flag.

        Returns:
            List of region metadata dictionaries.
        """
        regions: list[dict[str, Any]] = []
        for region_code, meta in SUPPORTED_REGIONS.items():
            if region_code not in settings.ALLOWED_REGIONS:
                continue
            regions.append(
                {
                    "region": region_code,
                    "name": meta["name"],
                    "short_name": meta["short_name"],
                    "enabled": meta["enabled"],
                    "is_default": region_code == settings.AWS_DEFAULT_REGION,
                }
            )
        return regions

    def get_vpcs(self, region: str) -> list[dict[str, Any]]:
        """Discover VPCs in a region via boto3 (with static fallback).

        Calls ``ec2.describe_vpcs()`` in the specified region.  If
        boto3 is not installed or AWS credentials are missing, returns
        static development data instead.

        Args:
            region: AWS region identifier (e.g. ``us-east-1``).

        Returns:
            List of VPC dictionaries, each containing ``vpc_id``,
            ``name``, ``cidr_block``, ``is_default``, and ``state``.

        Raises:
            ValueError: If the region is not supported.
        """
        if not self.validate_region(region):
            raise ValueError(
                f"Region '{region}' is not supported. "
                f"Supported: {', '.join(sorted(SUPPORTED_REGIONS))}"
            )

        try:
            return self._discover_vpcs_boto3(region)
        except Exception as exc:
            logger.info(
                "boto3 VPC discovery unavailable for %s (%s), using static data",
                region,
                exc,
            )
            return self._get_static_vpcs(region)

    def get_subnets(self, region: str, vpc_id: str) -> list[dict[str, Any]]:
        """Discover subnets in a VPC via boto3 (with static fallback).

        Calls ``ec2.describe_subnets()`` filtered by VPC ID.  Falls
        back to static data when AWS is unreachable.

        Args:
            region: AWS region identifier.
            vpc_id: VPC ID to filter subnets for.

        Returns:
            List of subnet dictionaries, each containing ``subnet_id``,
            ``name``, ``cidr_block``, ``availability_zone``,
            ``available_ips``, ``is_public``, and ``state``.

        Raises:
            ValueError: If the region is not supported.
        """
        if not self.validate_region(region):
            raise ValueError(
                f"Region '{region}' is not supported. "
                f"Supported: {', '.join(sorted(SUPPORTED_REGIONS))}"
            )

        try:
            return self._discover_subnets_boto3(region, vpc_id)
        except Exception as exc:
            logger.info(
                "boto3 subnet discovery unavailable for %s/%s (%s), using static data",
                region,
                vpc_id,
                exc,
            )
            return self._get_static_subnets(region, vpc_id)

    def get_availability_zones(self, region: str) -> list[dict[str, Any]]:
        """List availability zones in a region.

        Calls ``ec2.describe_availability_zones()`` in the specified
        region.  Falls back to static data when AWS is unreachable.

        Args:
            region: AWS region identifier.

        Returns:
            List of AZ dictionaries, each containing ``zone_name``,
            ``zone_id``, ``state``, and ``zone_type``.

        Raises:
            ValueError: If the region is not supported.
        """
        if not self.validate_region(region):
            raise ValueError(
                f"Region '{region}' is not supported. "
                f"Supported: {', '.join(sorted(SUPPORTED_REGIONS))}"
            )

        try:
            return self._discover_azs_boto3(region)
        except Exception as exc:
            logger.info(
                "boto3 AZ discovery unavailable for %s (%s), using static data",
                region,
                exc,
            )
            return self._get_static_azs(region)

    def validate_region(self, region: str) -> bool:
        """Check if a region is supported and enabled.

        A region must appear in ``SUPPORTED_REGIONS`` with
        ``enabled=True`` *and* be listed in the application's
        ``ALLOWED_REGIONS`` setting.

        Args:
            region: AWS region identifier.

        Returns:
            True if the region is valid and enabled.
        """
        meta = SUPPORTED_REGIONS.get(region)
        if meta is None:
            return False
        if not meta.get("enabled", False):
            return False
        if region not in settings.ALLOWED_REGIONS:
            return False
        return True

    # ------------------------------------------------------------------
    # boto3 live discovery
    # ------------------------------------------------------------------

    def _discover_vpcs_boto3(self, region: str) -> list[dict[str, Any]]:
        """Query AWS for VPCs in the given region via boto3."""
        import boto3

        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_vpcs(
            Filters=[{"Name": "state", "Values": ["available"]}]
        )

        vpcs: list[dict[str, Any]] = []
        for vpc in response.get("Vpcs", []):
            name = ""
            for tag in vpc.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break
            vpcs.append(
                {
                    "vpc_id": vpc["VpcId"],
                    "name": name,
                    "cidr_block": vpc["CidrBlock"],
                    "is_default": vpc.get("IsDefault", False),
                    "state": vpc["State"],
                }
            )

        logger.info("Discovered %d VPCs in %s via boto3", len(vpcs), region)
        return vpcs

    def _discover_subnets_boto3(
        self, region: str, vpc_id: str
    ) -> list[dict[str, Any]]:
        """Query AWS for subnets in the given VPC via boto3."""
        import boto3

        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_subnets(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )

        # To determine public vs private we check for a route table with
        # an internet gateway route. For simplicity in discovery we look
        # at MapPublicIpOnLaunch as a heuristic.
        subnets: list[dict[str, Any]] = []
        for subnet in response.get("Subnets", []):
            name = ""
            for tag in subnet.get("Tags", []):
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break
            subnets.append(
                {
                    "subnet_id": subnet["SubnetId"],
                    "name": name,
                    "cidr_block": subnet["CidrBlock"],
                    "availability_zone": subnet["AvailabilityZone"],
                    "available_ips": subnet.get("AvailableIpAddressCount", 0),
                    "is_public": subnet.get("MapPublicIpOnLaunch", False),
                    "state": subnet["State"],
                }
            )

        logger.info(
            "Discovered %d subnets in %s/%s via boto3",
            len(subnets),
            region,
            vpc_id,
        )
        return subnets

    def _discover_azs_boto3(self, region: str) -> list[dict[str, Any]]:
        """Query AWS for availability zones in the given region via boto3."""
        import boto3

        ec2 = boto3.client("ec2", region_name=region)
        response = ec2.describe_availability_zones(
            Filters=[
                {"Name": "region-name", "Values": [region]},
                {"Name": "state", "Values": ["available"]},
            ]
        )

        azs: list[dict[str, Any]] = []
        for az in response.get("AvailabilityZones", []):
            azs.append(
                {
                    "zone_name": az["ZoneName"],
                    "zone_id": az["ZoneId"],
                    "state": az["State"],
                    "zone_type": az.get("ZoneType", "availability-zone"),
                }
            )

        logger.info("Discovered %d AZs in %s via boto3", len(azs), region)
        return azs

    # ------------------------------------------------------------------
    # Static fallback data
    # ------------------------------------------------------------------

    def _get_static_vpcs(self, region: str) -> list[dict[str, Any]]:
        """Static VPC data for development without AWS credentials.

        Returns 2-3 realistic VPCs per region, including a default VPC,
        a production VPC, and a dev/staging VPC.

        Args:
            region: AWS region identifier.

        Returns:
            List of VPC dictionaries.
        """
        return _STATIC_VPCS.get(region, [])

    def _get_static_subnets(
        self, region: str, vpc_id: str
    ) -> list[dict[str, Any]]:
        """Static subnet data for development.

        Returns 3-4 subnets per VPC with a mix of public and private
        subnets across different availability zones.

        Args:
            region: AWS region identifier.
            vpc_id: VPC ID to look up subnets for.

        Returns:
            List of subnet dictionaries.
        """
        region_subnets = _STATIC_SUBNETS.get(region, {})
        return region_subnets.get(vpc_id, [])

    def _get_static_azs(self, region: str) -> list[dict[str, Any]]:
        """Static AZ data for development.

        Args:
            region: AWS region identifier.

        Returns:
            List of AZ dictionaries.
        """
        return _STATIC_AZS.get(region, [])
