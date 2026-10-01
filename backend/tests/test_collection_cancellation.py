from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from app.services.collection_lifecycle import platform_state
from app.services.search_service import SearchService


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class FakeDatabase:
    def __init__(self, job):
        self.job = job
        self.statements = []
        self.added = []
        self.flush_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return ScalarResult(self.job)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1


def make_job(status="running"):
    return SimpleNamespace(
        id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        name="Multi-platform collection",
        status=status,
        platforms=["twitter", "tiktok", "youtube"],
        platform_states={
            "twitter": platform_state("running"),
            "tiktok": platform_state("completed", posts_collected=25),
            "youtube": platform_state("pending"),
        },
        total_posts_collected=25,
        cancel_requested_at=None,
        cancel_requested_by=None,
        last_progress_at=datetime.now(timezone.utc),
    )


def make_actor(organization_id):
    return SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=organization_id,
        email="researcher@example.com",
    )


@pytest.mark.asyncio
async def test_cancel_job_is_owned_atomic_and_idempotent():
    organization_id = uuid.uuid4()
    job = make_job()
    actor = make_actor(organization_id)
    db = FakeDatabase(job)
    service = SearchService(db)

    first = await service.cancel_job(
        job.project_id,
        job.id,
        organization_id,
        actor,
    )
    first_requested_at = job.cancel_requested_at

    assert first["status"] == "cancelling"
    assert first["completed_platforms"] == ["tiktok"]
    assert first["cancelling_platforms"] == ["twitter", "youtube"]
    assert job.status == "cancelling"
    assert job.platform_states["twitter"]["status"] == "cancel_requested"
    assert job.platform_states["tiktok"]["posts_collected"] == 25
    assert job.cancel_requested_by == actor.id
    assert len(db.added) == 1
    assert "FOR UPDATE" in str(db.statements[0]).upper()
    assert "projects.organization_id" in str(db.statements[0])

    second = await service.cancel_job(
        job.project_id,
        job.id,
        organization_id,
        actor,
    )

    assert second == first
    assert job.cancel_requested_at == first_requested_at
    assert len(db.added) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "terminal_status",
    ["completed", "completed_with_errors", "cancelled", "failed"],
)
async def test_cancel_job_rejects_terminal_jobs(terminal_status):
    organization_id = uuid.uuid4()
    job = make_job(status=terminal_status)
    db = FakeDatabase(job)

    with pytest.raises(HTTPException) as error:
        await SearchService(db).cancel_job(
            job.project_id,
            job.id,
            organization_id,
            make_actor(organization_id),
        )

    assert error.value.status_code == 409
    assert error.value.detail == {
        "code": "COLLECTION_ALREADY_TERMINAL",
        "status": terminal_status,
    }
    assert job.cancel_requested_at is None
    assert db.added == []


@pytest.mark.asyncio
async def test_cancel_job_hides_missing_or_unauthorized_job():
    db = FakeDatabase(None)

    result = await SearchService(db).cancel_job(
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        make_actor(uuid.uuid4()),
    )

    assert result is None


@pytest.mark.asyncio
async def test_cancel_endpoint_requires_authentication(client):
    response = await client.post(
        f"/api/projects/{uuid.uuid4()}/jobs/{uuid.uuid4()}/cancel"
    )

    assert response.status_code in {401, 403}
