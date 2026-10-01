from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import logging
from fastapi import HTTPException, status
from app.models.project import Project
from app.models.search_job import SearchJob
from app.models.query_version import QueryVersion
from app.schemas.search_job import SearchJobCreate
from app.models.user import User
from app.services.activity_service import ActivityService
from app.services.query_validation import validate_query
from app.services.collection_lifecycle import (
    TERMINAL_JOB_STATUSES,
    platform_state,
    request_platform_cancellation,
)

PLATFORM_ALLOCATION_WEIGHTS = {
    "twitter": 0.05,
    "x": 0.05,
    "reddit": 0.05,
    "tiktok": 1.75,
    "youtube": 0.05,
    "instagram": 0.8,
    "pinterest": 0.8,
    "facebook": 0.5,
}

logger = logging.getLogger(__name__)


def allocate_post_counts(platforms: list[str], requested_total: int) -> dict[str, int]:
    unique_platforms = []
    for platform in platforms:
        normalized = platform.lower()
        if normalized and normalized not in unique_platforms:
            unique_platforms.append(normalized)
    if not unique_platforms:
        return {}

    requested_total = max(0, int(requested_total or 0))
    weights = {
        platform: PLATFORM_ALLOCATION_WEIGHTS.get(platform, 1.0)
        for platform in unique_platforms
    }
    total_weight = sum(weights.values())
    raw_allocations = {
        platform: requested_total * weight / total_weight
        for platform, weight in weights.items()
    }
    allocations = {
        platform: int(raw_allocations[platform])
        for platform in unique_platforms
    }
    remainder = requested_total - sum(allocations.values())
    for platform in sorted(
        unique_platforms,
        key=lambda item: (raw_allocations[item] - allocations[item], weights[item], item),
        reverse=True,
    )[:remainder]:
        allocations[platform] += 1
    return allocations


class SearchService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _verify_project(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> Optional[Project]:
        result = await self.db.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_job(
        self, project_id: uuid.UUID, data: SearchJobCreate, organization_id: uuid.UUID, actor: User | None = None
    ) -> dict:
        validate_query(data.query, data.platforms)
        project = await self._verify_project(project_id, organization_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        from app.models.collection_pull import CollectionPull
        from app.services.budget_service import comparison_allocations, FRESH_SECONDS
        import hashlib, json
        from datetime import timedelta
        fingerprint = hashlib.sha256(json.dumps({
            "query": data.query, "platforms": sorted(data.platforms),
            "date_from": data.date_from.isoformat() if data.date_from else None,
            "date_to": data.date_to.isoformat() if data.date_to else None,
        }, sort_keys=True).encode()).hexdigest()
        if data.pull_id:
            pull = (await self.db.execute(select(CollectionPull).where(
                CollectionPull.id == data.pull_id,
                CollectionPull.project_id == project_id).with_for_update())).scalar_one_or_none()
            if not pull:
                raise HTTPException(404, "Pull not found in this project")
            if pull.full_job_id:
                raise HTTPException(409, "This pull already has a full collection. Start a new pull explicitly.")
            if set(data.platforms) != set(pull.platforms):
                raise HTTPException(422, "Source selection is fixed for a pull. Start a new pull to change sources.")
        else:
            limits = {p: data.primary_credit_limit for p in data.platforms if p != "instagram"}
            limits.update(comparison_allocations(data.platforms, data.comparison_limit))
            pull = CollectionPull(project_id=project_id, platforms=data.platforms,
                comparison_limit=data.comparison_limit, platform_limits=limits, request_limit=data.request_limit)
            self.db.add(pull)
            await self.db.flush()
        active = (await self.db.execute(select(SearchJob).where(SearchJob.pull_id == pull.id,
            SearchJob.status.in_(["pending", "queued", "running", "cancelling"])))).scalars().first()
        if active:
            raise HTTPException(409, "Wait for the current preview or collection to finish before revising this pull")
        if data.mode == "preview":
            cached = (await self.db.execute(select(SearchJob).where(
                SearchJob.pull_id == pull.id, SearchJob.mode == "preview", SearchJob.fingerprint == fingerprint,
                SearchJob.status.in_(["completed", "completed_with_errors"]),
                SearchJob.completed_at >= datetime.now(timezone.utc) - timedelta(seconds=FRESH_SECONDS)
            ).order_by(SearchJob.created_at.desc()))).scalars().first()
            if cached:
                return await self._job_with_versions(cached)
        requested_post_count = data.requested_post_count or data.max_results_per_platform
        platform_allocations = allocate_post_counts(data.platforms, requested_post_count)
        if data.mode == "preview":
            platform_allocations = {p: min(20, n) for p, n in platform_allocations.items()}
        max_results_per_platform = max(platform_allocations.values())
        job = SearchJob(
            project_id=project_id, pull_id=pull.id, mode=data.mode, fingerprint=fingerprint,
            name=data.name, status="pending", platforms=data.platforms,
            date_from=data.date_from, date_to=data.date_to,
            max_results_per_platform=max_results_per_platform,
            requested_post_count=requested_post_count, platform_allocations=platform_allocations,
            platform_states={platform: platform_state("pending") for platform in data.platforms},
        )
        self.db.add(job)
        await self.db.flush()
        if data.mode == "collection":
            pull.full_job_id = job.id
        await ActivityService(self.db).log(
            organization_id=organization_id,
            project_id=project_id,
            actor=actor,
            action="collection_pull_started",
            target_type="search_job",
            target_id=str(job.id),
            target_label=project.name,
            metadata={"platforms": data.platforms, "requested_post_count": requested_post_count, "platform_allocations": platform_allocations},
        )

        # Create initial query version
        qv = QueryVersion(
            search_job_id=job.id,
            version_number=1,
            label="Initial Query",
            boolean_query=data.query,
            description="Auto-generated from search job creation",
            or_groups=[[data.query]],
            is_active=True,
        )
        self.db.add(qv)
        await self.db.flush()

        # Publish only after durable configuration. A dispatch failure leaves an inspectable failed run.
        task_id = str(uuid.uuid4())
        job.celery_task_id = task_id
        job.status = "queued"
        await self.db.commit()
        try:
            from app.workers.tasks import run_collection_job
            run_collection_job.apply_async(args=[str(job.id)], task_id=task_id, queue="collection")
        except Exception as exc:
            logger.error("Collection dispatch failed: job_id=%s type=%s", job.id, type(exc).__name__)
            job.status = "failed"
            job.error_message = "Queue unavailable. Check Redis and the collection worker, then start a new pull."
            await self.db.commit()
        await self.db.refresh(job)

        return await self._job_with_versions(job)

    async def list_jobs(self, project_id: uuid.UUID, organization_id: uuid.UUID) -> List[dict]:
        project = await self._verify_project(project_id, organization_id)
        if not project:
            return []
        result = await self.db.execute(
            select(SearchJob)
            .where(SearchJob.project_id == project_id)
            .options(selectinload(SearchJob.query_versions))
            .order_by(SearchJob.created_at.desc())
        )
        jobs = result.scalars().all()
        return [await self._job_with_versions(j) for j in jobs]

    async def get_job(
        self, project_id: uuid.UUID, job_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Optional[dict]:
        project = await self._verify_project(project_id, organization_id)
        if not project:
            return None
        result = await self.db.execute(
            select(SearchJob)
            .where(SearchJob.id == job_id, SearchJob.project_id == project_id)
            .options(selectinload(SearchJob.query_versions))
        )
        job = result.scalar_one_or_none()
        if not job:
            return None
        return await self._job_with_versions(job)

    async def cancel_job(
        self,
        project_id: uuid.UUID,
        job_id: uuid.UUID,
        organization_id: uuid.UUID,
        actor: User,
    ) -> Optional[dict]:
        result = await self.db.execute(
            select(SearchJob)
            .join(Project, Project.id == SearchJob.project_id)
            .where(
                SearchJob.id == job_id,
                SearchJob.project_id == project_id,
                Project.organization_id == organization_id,
            )
            .with_for_update()
        )
        job = result.scalar_one_or_none()
        if not job:
            return None

        if job.status in TERMINAL_JOB_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "COLLECTION_ALREADY_TERMINAL",
                    "status": job.status,
                },
            )

        if job.status not in {"pending", "queued", "running", "cancelling"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "COLLECTION_NOT_CANCELLABLE",
                    "status": job.status,
                },
            )

        (
            updated_states,
            completed_platforms,
            cancelling_platforms,
        ) = request_platform_cancellation(
            list(job.platforms or []),
            dict(job.platform_states or {}),
        )

        if job.status != "cancelling":
            requested_at = datetime.now(timezone.utc)
            job.status = "cancelling"
            job.platform_states = updated_states
            job.cancel_requested_at = requested_at
            job.cancel_requested_by = actor.id
            job.last_progress_at = requested_at
            await ActivityService(self.db).log(
                organization_id=organization_id,
                project_id=project_id,
                actor=actor,
                action="collection_cancel_requested",
                target_type="search_job",
                target_id=str(job.id),
                target_label=job.name,
                metadata={
                    "completed_platforms": completed_platforms,
                    "cancelling_platforms": cancelling_platforms,
                    "posts_preserved": job.total_posts_collected,
                },
            )
            await self.db.flush()

        return {
            "job_id": job.id,
            "status": "cancelling",
            "cancel_requested_at": job.cancel_requested_at,
            "cancel_requested_by": job.cancel_requested_by,
            "completed_platforms": completed_platforms,
            "cancelling_platforms": cancelling_platforms,
        }

    async def _job_with_versions(self, job: SearchJob) -> dict:
        result = await self.db.execute(
            select(QueryVersion).where(QueryVersion.search_job_id == job.id)
        )
        versions = result.scalars().all()
        from app.models.collection_pull import CollectionPull, RunPost
        from app.models.normalized_post import NormalizedPost
        from app.services.budget_service import usage_summary
        pull = await self.db.get(CollectionPull, job.pull_id) if job.pull_id else None
        examples = []
        if job.mode == "preview":
            rows = (await self.db.execute(select(NormalizedPost).join(RunPost, RunPost.post_id == NormalizedPost.id)
                .where(RunPost.job_id == job.id).order_by(NormalizedPost.platform, NormalizedPost.published_at).limit(120))).scalars().all()
            examples = [{"id": str(p.id), "platform": p.platform, "body": p.body, "url": p.url,
                "published_at": p.published_at.isoformat() if p.published_at else None} for p in rows]
        d = {
            "pull_id": job.pull_id, "mode": job.mode,
            "usage": await usage_summary(self.db, pull) if pull else {},
            "preview_examples": examples,
            "id": job.id,
            "project_id": job.project_id,
            "name": job.name,
            "status": job.status,
            "platforms": job.platforms,
            "date_from": job.date_from,
            "date_to": job.date_to,
            "max_results_per_platform": job.max_results_per_platform,
            "requested_post_count": job.requested_post_count,
            "platform_allocations": job.platform_allocations or {},
            "platform_states": job.platform_states or {},
            "total_posts_collected": job.total_posts_collected,
            "error_message": job.error_message,
            "celery_task_id": job.celery_task_id,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "cancel_requested_at": job.cancel_requested_at,
            "cancelled_at": job.cancelled_at,
            "cancel_requested_by": job.cancel_requested_by,
            "last_progress_at": job.last_progress_at,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "query_versions": [
                {
                    "id": v.id,
                    "version_number": v.version_number,
                    "label": v.label,
                    "boolean_query": v.boolean_query,
                    "description": v.description,
                    "or_groups": v.or_groups,
                    "is_active": v.is_active,
                    "created_at": v.created_at,
                }
                for v in versions
            ],
        }
        return d
