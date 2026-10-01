from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy.dialects import postgresql

from app.services.abandoned_jobs import (
    ABANDONED_JOB_ERROR,
    ABANDONED_PLATFORM_ERROR,
    finalize_abandoned_job,
    reconcile_abandoned_jobs,
    stale_collection_jobs_query,
)
from app.services.collection_lifecycle import platform_state
from app.workers.celery_app import celery_app
from app.workers.tasks import (
    _active_celery_task_ids,
    reconcile_abandoned_collection_jobs,
)


def make_job(
    *,
    status="running",
    platforms=None,
    platform_states=None,
    celery_task_id="collection-task-1",
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        platforms=platforms or ["twitter", "tiktok"],
        platform_states=platform_states
        or {
            "twitter": platform_state("running", posts_collected=0),
            "tiktok": platform_state("pending", posts_collected=0),
        },
        celery_task_id=celery_task_id,
        total_posts_collected=0,
        error_message=None,
        completed_at=None,
        cancelled_at=None,
        last_progress_at=None,
    )


class ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def all(self):
        return self.value

    def scalar_one(self):
        return self.value


class RecordingDatabase:
    def __init__(self, jobs, post_counts):
        self.results = [ScalarResult(jobs)]
        self.results.extend(ScalarResult(count) for count in post_counts)
        self.statements = []
        self.commits = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)

    async def commit(self):
        self.commits += 1


def test_stale_query_never_selects_recent_or_terminal_jobs():
    cutoff = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    statement = stale_collection_jobs_query(cutoff, 25)
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    assert "search_jobs.status in ('running', 'cancelling')" in sql
    assert "coalesce(search_jobs.last_progress_at" in sql
    assert "< '2026-07-28 12:00:00+00:00'" in sql
    assert "limit 25" in sql
    assert "for update skip locked" in sql


def test_stale_running_job_with_committed_posts_completes_with_errors():
    recovered_at = datetime.now(timezone.utc)
    job = make_job(
        platform_states={
            "twitter": platform_state("completed", posts_collected=17),
            "tiktok": platform_state("running", posts_collected=0),
        }
    )

    recovered = finalize_abandoned_job(
        job,
        total_posts=17,
        recovered_at=recovered_at,
    )

    assert recovered.status == "completed_with_errors"
    assert recovered.total_posts == 17
    assert job.total_posts_collected == 17
    assert job.platform_states["twitter"]["status"] == "completed"
    assert job.platform_states["twitter"]["posts_collected"] == 17
    assert job.platform_states["tiktok"]["status"] == "failed"
    assert job.platform_states["tiktok"]["error"] == ABANDONED_PLATFORM_ERROR
    assert job.error_message == ABANDONED_JOB_ERROR
    assert job.completed_at == recovered_at


def test_empty_abandoned_running_job_fails():
    recovered_at = datetime.now(timezone.utc)
    job = make_job()

    recovered = finalize_abandoned_job(
        job,
        total_posts=0,
        recovered_at=recovered_at,
    )

    assert recovered.status == "failed"
    assert all(
        state["status"] == "failed"
        for state in job.platform_states.values()
    )


def test_stale_cancelling_job_becomes_cancelled_and_preserves_results():
    recovered_at = datetime.now(timezone.utc)
    job = make_job(
        status="cancelling",
        platform_states={
            "twitter": platform_state("completed", posts_collected=21),
            "tiktok": platform_state("cancel_requested", posts_collected=0),
        },
    )

    recovered = finalize_abandoned_job(
        job,
        total_posts=21,
        recovered_at=recovered_at,
    )

    assert recovered.status == "cancelled"
    assert job.cancelled_at == recovered_at
    assert job.platform_states["twitter"]["status"] == "completed"
    assert job.platform_states["twitter"]["posts_collected"] == 21
    assert job.platform_states["tiktok"]["status"] == "cancelled"
    assert job.total_posts_collected == 21


@pytest.mark.asyncio
async def test_active_celery_job_is_not_recovered_even_when_stale():
    active_job = make_job(celery_task_id="still-active")
    abandoned_job = make_job(celery_task_id="gone")
    database = RecordingDatabase([active_job, abandoned_job], [8])
    now = datetime.now(timezone.utc)

    recovered = await reconcile_abandoned_jobs(
        database,
        stale_before=now - timedelta(minutes=15),
        recovered_at=now,
        batch_size=100,
        active_task_ids={"still-active"},
    )

    assert [item.job_id for item in recovered] == [abandoned_job.id]
    assert active_job.status == "running"
    assert active_job.completed_at is None
    assert abandoned_job.status == "completed_with_errors"
    assert abandoned_job.total_posts_collected == 8
    assert database.commits == 1
    assert len(database.statements) == 2


@pytest.mark.asyncio
async def test_no_stale_candidates_makes_no_changes_or_commit():
    database = RecordingDatabase([], [])
    now = datetime.now(timezone.utc)

    recovered = await reconcile_abandoned_jobs(
        database,
        stale_before=now - timedelta(minutes=15),
        recovered_at=now,
        batch_size=100,
        active_task_ids=set(),
    )

    assert recovered == []
    assert database.commits == 0
    assert len(database.statements) == 1


def test_celery_inspection_returns_active_task_ids(monkeypatch):
    inspector = SimpleNamespace(
        active=lambda: {
            "worker-1": [{"id": "task-a"}, {"id": "task-b"}],
            "worker-2": [{"id": "task-c"}],
        }
    )
    monkeypatch.setattr(
        celery_app.control,
        "inspect",
        lambda **kwargs: inspector,
    )

    assert _active_celery_task_ids() == {"task-a", "task-b", "task-c"}


def test_reconciler_is_periodic_and_routed_to_default_queue():
    task_name = "app.workers.tasks.reconcile_abandoned_collection_jobs"
    schedule = celery_app.conf.beat_schedule[
        "reconcile-abandoned-collection-jobs"
    ]

    assert schedule["task"] == task_name
    assert schedule["schedule"] > 0
    assert schedule["options"]["expires"] == schedule["schedule"]
    assert celery_app.conf.task_routes[task_name]["queue"] == "default"


def test_recovered_jobs_report_results_without_paid_enrichment(monkeypatch):
    recovered_job = SimpleNamespace(job_id=uuid.uuid4(), status="completed_with_errors", total_posts=12)
    monkeypatch.setattr("app.workers.tasks._active_celery_task_ids", lambda: set())
    monkeypatch.setattr("app.workers.tasks._run_async", lambda coroutine: (coroutine.close(), [recovered_job])[1])
    assert reconcile_abandoned_collection_jobs.run() == {"recovered":1,"jobs":[str(recovered_job.job_id)]}
