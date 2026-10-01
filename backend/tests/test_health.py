"""Tests for the health endpoint — these are integration tests requiring Docker."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "SocialScope API"
    assert "version" in data
