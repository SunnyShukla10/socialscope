"""Tests for project CRUD endpoints."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, seed_org_and_user, auth_headers):
    response = await client.post(
        "/api/projects",
        headers=auth_headers,
        json={
            "name": "Test Project",
            "description": "A test research project",
        },
    )
    assert response.status_code in (200, 201)
    data = response.json()
    assert data["name"] == "Test Project"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, seed_org_and_user, auth_headers):
    # Create two projects
    for i in range(2):
        await client.post(
            "/api/projects",
            headers=auth_headers,
            json={"name": f"Project {i}", "description": f"Description {i}"},
        )
    response = await client.get("/api/projects", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_get_project_detail(client: AsyncClient, seed_org_and_user, auth_headers):
    # Create a project
    create_resp = await client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "Detail Project", "description": "Check detail view"},
    )
    project_id = create_resp.json()["id"]

    # Get detail
    response = await client.get(f"/api/projects/{project_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Detail Project"


@pytest.mark.asyncio
async def test_create_project_unauthorized(client: AsyncClient):
    response = await client.post(
        "/api/projects",
        json={"name": "Unauth Project"},
    )
    assert response.status_code in (401, 403)
