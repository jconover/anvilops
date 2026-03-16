"""Cost estimation API endpoints.

Provides real-time monthly and annual cost estimates for server
configurations.  The frontend calls these endpoints during the server
builder wizard's "Review" step so the user sees a price breakdown
before clicking "Build".
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class StorageConfig(BaseModel):
    """A single additional EBS volume attached to the server."""

    drive_letter: str | None = Field(
        None, description="Drive letter (Windows only, e.g. D:)"
    )
    mount_point: str | None = Field(
        None, description="Mount point (Linux only, e.g. /data)"
    )
    size_gb: int = Field(..., ge=1, le=16384, description="Volume size in GB")
    volume_type: Literal["gp3", "io2"] = "gp3"


class CostEstimateRequest(BaseModel):
    """Input payload for the cost estimation endpoint.

    Mirrors the fields from ``ServerCreateRequest`` that affect pricing.
    """

    instance_size: Literal["small", "medium", "large", "xl"]
    os_type: Literal[
        "windows_2022", "windows_2019",
        "amazon_linux_2023", "ubuntu_2204", "rhel_9",
    ]
    region: str = "us-east-1"
    additional_storage: list[StorageConfig] = []


class CostLineItem(BaseModel):
    """A single row in the cost breakdown table."""

    category: str = Field(
        ..., description='Cost category: "Compute", "Storage", or "License"'
    )
    description: str = Field(
        ..., description='Human-readable line, e.g. "t3.medium On-Demand (730 hrs)"'
    )
    monthly_cost: float = Field(
        ..., description="Monthly cost in USD for this line item"
    )


class CostEstimateResponse(BaseModel):
    """Full cost estimate returned by ``POST /costs/estimate``."""

    instance_cost: float = Field(..., description="Monthly compute cost (USD)")
    storage_cost: float = Field(..., description="Monthly EBS storage cost (USD)")
    os_license_cost: float = Field(
        ..., description="Monthly OS license surcharge (0 for base Linux)"
    )
    total_monthly: float = Field(..., description="Total monthly cost (USD)")
    total_annual: float = Field(..., description="Projected annual cost (USD)")
    currency: str = "USD"
    instance_type: str = Field(
        ..., description="Resolved AWS instance type, e.g. t3.medium"
    )
    breakdown: list[CostLineItem]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/estimate",
    response_model=CostEstimateResponse,
    summary="Estimate server cost",
    description=(
        "Accept a partial server configuration and return a detailed "
        "monthly and annual cost estimate with line-item breakdown."
    ),
)
async def estimate_cost(user: CurrentUser, request: CostEstimateRequest) -> CostEstimateResponse:
    """Calculate a cost estimate for the given server configuration.

    The request only needs the pricing-relevant fields (instance size,
    OS, region, additional storage).  Returns the total monthly and
    annual cost together with a per-line breakdown so the frontend can
    render a cost summary card.
    """
    from app.services.cost_estimator import CostEstimator

    estimator = CostEstimator()

    try:
        result = estimator.estimate(
            {
                "instance_size": request.instance_size,
                "os_type": request.os_type,
                "region": request.region,
                "additional_storage": [
                    s.model_dump() for s in request.additional_storage
                ],
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return CostEstimateResponse(
        instance_cost=result["instance_cost"],
        storage_cost=result["storage_cost"],
        os_license_cost=result["os_license_cost"],
        total_monthly=result["total_monthly"],
        total_annual=result["total_annual"],
        currency=result["currency"],
        instance_type=result["instance_type"],
        breakdown=[CostLineItem(**item) for item in result["breakdown"]],
    )


@router.get(
    "/pricing",
    summary="Get pricing table",
    description=(
        "Return the full static pricing data so the frontend can "
        "display instance-type cards, storage rates, and surcharges "
        "without making per-config estimate calls."
    ),
)
async def get_pricing_table(user: CurrentUser) -> dict:
    """Return the complete pricing table for frontend display.

    This powers the pricing reference section of the server builder
    wizard so users can compare instance sizes and storage options
    before filling out the form.
    """
    from app.services.cost_estimator import CostEstimator

    estimator = CostEstimator()
    return estimator.get_pricing_table()
