"""Integration tests for the /api/v1/costs endpoints.

These hit the real FastAPI routes via an in-process ASGI transport,
but the cost endpoints use only the static CostEstimator class --
no database, Redis, or external APIs are needed.
"""

import pytest

# ------------------------------------------------------------------
# POST /api/v1/costs/estimate
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_estimate_endpoint_basic(client):
    """POST a minimal config and verify the total_monthly value."""
    response = await client.post(
        "/api/v1/costs/estimate",
        json={
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["instance_cost"] == 30.37
    assert data["storage_cost"] == 2.40
    assert data["os_license_cost"] == 0.0
    assert data["total_monthly"] == 32.77


@pytest.mark.asyncio
async def test_estimate_endpoint_with_storage(client):
    """Additional storage volumes are reflected in storage_cost."""
    response = await client.post(
        "/api/v1/costs/estimate",
        json={
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
            "additional_storage": [
                {"size_gb": 100, "volume_type": "gp3"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Root: 30*0.08=2.4, additional: 100*0.08=8.0
    assert data["storage_cost"] == 10.40
    assert data["total_monthly"] == 40.77


@pytest.mark.asyncio
async def test_estimate_endpoint_windows(client):
    """Windows OS should produce a non-zero os_license_cost."""
    response = await client.post(
        "/api/v1/costs/estimate",
        json={
            "instance_size": "small",
            "os_type": "windows_2022",
            "region": "us-east-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["os_license_cost"] > 0
    assert data["os_license_cost"] == 8.76  # 0.012 * 730


@pytest.mark.asyncio
async def test_estimate_endpoint_invalid_size(client):
    """An unsupported instance_size should be rejected with 422."""
    response = await client.post(
        "/api/v1/costs/estimate",
        json={
            "instance_size": "micro",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_estimate_endpoint_invalid_os(client):
    """An unsupported os_type should be rejected with 422 by Pydantic."""
    response = await client.post(
        "/api/v1/costs/estimate",
        json={
            "instance_size": "small",
            "os_type": "centos",
            "region": "us-east-1",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_estimate_endpoint_response_structure(client):
    """All expected keys must be present in the response body."""
    response = await client.post(
        "/api/v1/costs/estimate",
        json={
            "instance_size": "small",
            "os_type": "amazon_linux_2023",
            "region": "us-east-1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    expected_keys = {
        "instance_cost",
        "storage_cost",
        "os_license_cost",
        "total_monthly",
        "total_annual",
        "currency",
        "instance_type",
        "breakdown",
    }
    assert set(data.keys()) == expected_keys
    assert isinstance(data["breakdown"], list)
    assert len(data["breakdown"]) >= 1


# ------------------------------------------------------------------
# GET /api/v1/costs/pricing
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pricing_endpoint_basic(client):
    """GET pricing returns 200 and the expected top-level keys."""
    response = await client.get("/api/v1/costs/pricing")
    assert response.status_code == 200
    data = response.json()
    assert "regions" in data
    assert "sizes" in data
    assert "ebs" in data


@pytest.mark.asyncio
async def test_pricing_endpoint_currency(client):
    """Pricing response must include currency=USD."""
    response = await client.get("/api/v1/costs/pricing")
    assert response.status_code == 200
    data = response.json()
    assert data["currency"] == "USD"
