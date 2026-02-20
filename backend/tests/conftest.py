import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.cost_estimator import CostEstimator
from app.services.scaling import ScalingService


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def cost_estimator():
    return CostEstimator()


@pytest.fixture
def scaling_service():
    return ScalingService()
