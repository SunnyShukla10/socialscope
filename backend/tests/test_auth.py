"""Tests for authentication endpoints."""
import pytest
from httpx import AsyncClient
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from app.config import settings


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seed_org_and_user):
    _, user, password = seed_org_and_user
    response = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, seed_org_and_user):
    _, user, _ = seed_org_and_user
    response = await client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "wrongpassword"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_token(client: AsyncClient, seed_org_and_user, auth_headers):
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["full_name"] == "Test User"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_me_without_token(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_me_with_invalid_token(client: AsyncClient):
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid_token_here"},
    )
    assert response.status_code == 401


def standard_hs256_token(payload):
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).rstrip(b'=')
    signing_input = encode({'alg': 'HS256', 'typ': 'JWT'}) + b'.' + encode(payload)
    signature = hmac.new(settings.SECRET_KEY.encode(), signing_input, hashlib.sha256).digest()
    return (signing_input + b'.' + base64.urlsafe_b64encode(signature).rstrip(b'=')).decode()


@pytest.mark.asyncio
async def test_standard_existing_hs256_sessions_survive_jwt_library_change(client, seed_org_and_user):
    _, user, _ = seed_org_and_user
    token = standard_hs256_token({'sub': str(user.id), 'ver': user.token_version,
        'exp': int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())})
    assert (await client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token})).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize('expiry', [None, 1])
async def test_sessions_require_unexpired_expiry(client, seed_org_and_user, expiry):
    _, user, _ = seed_org_and_user
    payload = {'sub': str(user.id), 'ver': user.token_version}
    if expiry is not None:
        payload['exp'] = expiry
    token = standard_hs256_token(payload)
    assert (await client.get('/api/auth/me', headers={'Authorization': 'Bearer ' + token})).status_code == 401
