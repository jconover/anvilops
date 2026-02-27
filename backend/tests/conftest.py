from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.cost_estimator import CostEstimator
from app.services.scaling import ScalingService


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def cost_estimator() -> CostEstimator:
    return CostEstimator()


@pytest.fixture
def scaling_service() -> ScalingService:
    return ScalingService()
