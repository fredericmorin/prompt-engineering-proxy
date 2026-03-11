import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] is True
    assert "redis" in data


@pytest.mark.asyncio
async def test_health_returns_json(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["content-type"] == "application/json"
