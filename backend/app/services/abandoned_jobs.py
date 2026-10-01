from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import func, select

from app.models.collection_pull import RunPost
from app.models.search_job import SearchJob
from app.services.collection_lifecycle import (
    TERMINAL_PLATFORM_STATUSES,
    finalize_platform_cancellation,
    platform_state,
)


ABANDONED_JOB_ERROR = "Collection worker stopped before the job finished"
ABANDONED_PLATFORM_ERROR = "Collection worker stopped before this platform finished"


@dataclass(frozen=True)
class RecoveredJob:
    job_id: uuid.UUID
    status: str
    total_posts: int


def stale_collection_jobs_query(stale_before: datetime, batch_size: int):
    """Select only inactive-looking jobs old enough for conservative recovery."""
    last_activity = func.coalesce(
        SearchJob.last_progress_at,
        SearchJob.started_at,
        SearchJob.updated_at,
        SearchJob.created_at,
    )
    return (
        select(SearchJob)
        .where(
            SearchJob.status.in_(("running", "cancelling")),
            last_activity < stale_before,
        )
        .order_by(last_activity.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )


def _unfinished_platforms_failed(job: SearchJob, recovered_at: datetime) -> dict:
    states = {
        key: dict(value)
        for key, value in (job.platform_states or {}).items()
    }
    for configured_platform in job.platforms or []:
        platform = str(configured_platform).lower()
        state_key = next(
            (key for key in states if str(key).lower() == platform),
            platform,
        )
        state = dict(states.get(state_key) or platform_state("pending"))
        if state.get("status") not in TERMINAL_PLATFORM_STATUSES:
            state["status"] = "failed"
            state["completed_at"] = recovered_at.isoformat()
            state["last_progress_at"] = recovered_at.isoformat()
            state["error"] = ABANDONED_PLATFORM_ERROR
            states[state_key] = state
    return states


def finalize_abandoned_job(
    job: SearchJob,
    *,
    total_posts: int,
    recovered_at: datetime,
) -> RecoveredJob:
    """Finalize one locked stale job while retaining all committed state."""
    original_status = job.status
    if original_status == "cancelling":
        terminal_status = "cancelled"
        job.platform_states = finalize_platform_cancellation(
            list(job.platforms or []),
            dict(job.platform_states or {}),
            cancelled_at=recovered_at,
        )
        job.cancelled_at = recovered_at
    else:
        job.platform_states = _unfinished_platforms_failed(job, recovered_at)
        completed_platforms = sum(
            1
            for state in job.platform_states.values()
            if state.get("status") == "completed"
        )
        terminal_status = (
            "completed_with_errors"
            if total_posts > 0 or completed_platforms > 0
            else "failed"
        )
        if ABANDONED_JOB_ERROR not in (job.error_message or ""):
            job.error_message = "; ".join(
                message
                for message in (job.error_message, ABANDONED_JOB_ERROR)
                if message
            )

    job.status = terminal_status
    job.total_posts_collected = int(total_posts)
    job.completed_at = recovered_at
    job.last_progress_at = recovered_at
    return RecoveredJob(
        job_id=job.id,
        status=terminal_status,
        total_posts=int(total_posts),
    )


async def reconcile_abandoned_jobs(
    db,
    *,
    stale_before: datetime,
    recovered_at: datetime,
    batch_size: int,
    active_task_ids: Optional[set[str]] = None,
) -> list[RecoveredJob]:
    """
    Recover stale jobs not reported active by Celery.

    ``active_task_ids=None`` means worker inspection was unavailable. The stale
    threshold remains the safety boundary in that case.
    """
    result = await db.execute(
        stale_collection_jobs_query(stale_before, batch_size)
    )
    candidates = result.scalars().all()
    recovered: list[RecoveredJob] = []

    for job in candidates:
        if (
            active_task_ids is not None
            and job.celery_task_id
            and job.celery_task_id in active_task_ids
        ):
            continue

        total_posts = (
            await db.execute(
                select(func.count(RunPost.post_id)).where(
                    RunPost.job_id == job.id
                )
            )
        ).scalar_one()
        recovered.append(
            finalize_abandoned_job(
                job,
                total_posts=total_posts,
                recovered_at=recovered_at,
            )
        )

    if recovered:
        await db.commit()
    return recovered
