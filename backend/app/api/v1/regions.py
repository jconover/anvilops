"""Region discovery API endpoints.

Provides region, VPC, subnet, and availability zone lookups for the
server builder wizard.  The frontend calls these endpoints to populate
network selection dropdowns when a user picks a target region.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class RegionResponse(BaseModel):
    """A single supported AWS region."""

    region: str = Field(..., description="AWS region code, e.g. us-east-1")
    name: str = Field(
        ..., description="Full display name, e.g. US East (N. Virginia)"
    )
    short_name: str = Field(
        ..., description="Short display name, e.g. Virginia"
    )
    enabled: bool = Field(
        ..., description="Whether this region is currently enabled"
    )
    is_default: bool = Field(
        ..., description="Whether this is the default region"
    )


class RegionListResponse(BaseModel):
    """List of supported regions."""

    regions: list[RegionResponse]
    total: int


class VpcResponse(BaseModel):
    """A VPC discovered in an AWS region."""

    vpc_id: str = Field(..., description="VPC identifier")
    name: str = Field(..., description="Name tag value (may be empty)")
    cidr_block: str = Field(..., description="IPv4 CIDR block")
    is_default: bool = Field(
        ..., description="Whether this is the default VPC"
    )
    state: str = Field(..., description="VPC state (available, pending, etc.)")


class VpcListResponse(BaseModel):
    """List of VPCs in a region."""

    region: str
    vpcs: list[VpcResponse]
    total: int


class SubnetResponse(BaseModel):
    """A subnet discovered in an AWS VPC."""

    subnet_id: str = Field(..., description="Subnet identifier")
    name: str = Field(..., description="Name tag value (may be empty)")
    cidr_block: str = Field(..., description="IPv4 CIDR block")
    availability_zone: str = Field(
        ..., description="AZ the subnet resides in"
    )
    available_ips: int = Field(
        ..., description="Number of available IP addresses"
    )
    is_public: bool = Field(
        ...,
        description="Whether the subnet auto-assigns public IPs",
    )
    state: str = Field(
        ..., description="Subnet state (available, pending, etc.)"
    )


class SubnetListResponse(BaseModel):
    """List of subnets in a VPC."""

    region: str
    vpc_id: str
    subnets: list[SubnetResponse]
    total: int


class AvailabilityZoneResponse(BaseModel):
    """An availability zone in an AWS region."""

    zone_name: str = Field(..., description="AZ name, e.g. us-east-1a")
    zone_id: str = Field(..., description="AZ ID, e.g. use1-az1")
    state: str = Field(..., description="AZ state (available, etc.)")
    zone_type: str = Field(
        ..., description="Zone type (availability-zone, local-zone, etc.)"
    )


class AvailabilityZoneListResponse(BaseModel):
    """List of availability zones in a region."""

    region: str
    availability_zones: list[AvailabilityZoneResponse]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/",
    response_model=RegionListResponse,
    summary="List supported regions",
    description=(
        "Return all AWS regions that AnvilOps supports for server "
        "provisioning. Only enabled regions appear by default."
    ),
)
async def list_regions() -> RegionListResponse:
    """List all supported and enabled AWS regions.

    The response drives the region selector dropdown in the server
    builder wizard.  The default region is flagged so the frontend
    can pre-select it.
    """
    from app.services.regions import RegionService

    service = RegionService()
    regions = service.get_regions()

    return RegionListResponse(
        regions=[RegionResponse(**r) for r in regions],
        total=len(regions),
    )


@router.get(
    "/{region}/vpcs",
    response_model=VpcListResponse,
    summary="List VPCs in a region",
    description=(
        "Discover VPCs in the specified AWS region. Uses live AWS "
        "discovery when credentials are available, otherwise returns "
        "static development data."
    ),
)
async def list_vpcs(region: str) -> VpcListResponse:
    """List VPCs available in the given region.

    The server builder wizard calls this endpoint after the user selects
    a region so the VPC dropdown can be populated dynamically.
    """
    from app.services.regions import RegionService

    service = RegionService()

    if not service.validate_region(region):
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region}' is not supported or not enabled",
        )

    vpcs = service.get_vpcs(region)

    return VpcListResponse(
        region=region,
        vpcs=[VpcResponse(**v) for v in vpcs],
        total=len(vpcs),
    )


@router.get(
    "/{region}/vpcs/{vpc_id}/subnets",
    response_model=SubnetListResponse,
    summary="List subnets in a VPC",
    description=(
        "Discover subnets in the specified VPC within the given region. "
        "Returns subnet metadata including availability zone, CIDR block, "
        "available IP count, and public/private classification."
    ),
)
async def list_subnets(region: str, vpc_id: str) -> SubnetListResponse:
    """List subnets in the given VPC and region.

    The server builder wizard calls this endpoint after the user selects
    a VPC so the subnet dropdown can be populated.  The ``is_public``
    flag helps the wizard warn users about public subnet placement.
    """
    from app.services.regions import RegionService

    service = RegionService()

    if not service.validate_region(region):
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region}' is not supported or not enabled",
        )

    subnets = service.get_subnets(region, vpc_id)

    if not subnets:
        raise HTTPException(
            status_code=404,
            detail=f"No subnets found for VPC '{vpc_id}' in region '{region}'",
        )

    return SubnetListResponse(
        region=region,
        vpc_id=vpc_id,
        subnets=[SubnetResponse(**s) for s in subnets],
        total=len(subnets),
    )


@router.get(
    "/{region}/availability-zones",
    response_model=AvailabilityZoneListResponse,
    summary="List availability zones",
    description=(
        "List all available availability zones in the specified region."
    ),
)
async def list_availability_zones(
    region: str,
) -> AvailabilityZoneListResponse:
    """List availability zones in the given region.

    Used by the server builder wizard when the user needs to pick
    a specific AZ for placement (e.g. to co-locate with existing
    infrastructure).
    """
    from app.services.regions import RegionService

    service = RegionService()

    if not service.validate_region(region):
        raise HTTPException(
            status_code=404,
            detail=f"Region '{region}' is not supported or not enabled",
        )

    azs = service.get_availability_zones(region)

    return AvailabilityZoneListResponse(
        region=region,
        availability_zones=[AvailabilityZoneResponse(**az) for az in azs],
        total=len(azs),
    )
