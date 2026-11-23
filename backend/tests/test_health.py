"""API readiness checks using isolated fixtures and mocked dependencies."""
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from app.database import get_db
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "SocialScope API"
    assert "version" in data


@pytest.mark.asyncio
async def test_public_version_is_consistent(client, auth_headers):
    root = await client.get('/')
    sources = await client.get('/api/sources', headers=auth_headers)
    assert sources.status_code == 200
    assert sources.json()['version'] == root.json()['version'] == app.version
    assert 'pilot' not in sources.json()['version']


@pytest.mark.asyncio
@pytest.mark.parametrize('database_ok,redis_ok', [(True, True), (False, True), (True, False), (False, False)])
async def test_readiness_status_matches_dependencies(client, database_ok, redis_ok):
    db = AsyncMock()
    redis = AsyncMock()
    if not database_ok:
        db.execute.side_effect = RuntimeError('database unavailable')
    if not redis_ok:
        redis.ping.side_effect = RuntimeError('redis unavailable')
    async def override_db():
        yield db
    with patch.dict(app.dependency_overrides, {get_db: override_db}), patch(
            'app.routes.health.aioredis.from_url', return_value=redis):
        response = await client.get('/api/health')
    healthy = database_ok and redis_ok
    assert response.status_code == (200 if healthy else 503)
    assert response.json() == {'status': 'ok' if healthy else 'degraded',
                               'database': database_ok, 'redis': redis_ok}
    redis.aclose.assert_awaited_once()
    if not database_ok:
        db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_dependency_timeout_returns_degraded_and_closes_redis(client):
    db, redis = AsyncMock(), AsyncMock()
    async def override_db():
        yield db
    async def timed_out_ping():
        raise TimeoutError('dependency timeout')
    redis.ping.side_effect = timed_out_ping
    with patch.dict(app.dependency_overrides, {get_db: override_db}), patch(
            'app.routes.health.aioredis.from_url', return_value=redis):
        response = await client.get('/api/health')
    assert response.status_code == 503 and response.json()['redis'] is False
    redis.aclose.assert_awaited_once()
