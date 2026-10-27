import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_event import ActivityEvent
from app.models.user import User


class ActivityService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        *,
        organization_id: uuid.UUID,
        action: str,
        target_type: str,
        project_id: Optional[uuid.UUID] = None,
        actor: Optional[User] = None,
        actor_label: Optional[str] = None,
        target_id: Optional[str] = None,
        target_label: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ActivityEvent:
        event = ActivityEvent(
            organization_id=organization_id,
            project_id=project_id,
            actor_user_id=actor.id if actor else None,
            actor_label=actor_label or (actor.email if actor else "System"),
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_label=target_label,
            extra_metadata=metadata or {},
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def latest(self, organization_id: uuid.UUID, limit: int = 100,
                     offset: int = 0, user_id: uuid.UUID | None = None) -> list[ActivityEvent]:
        conditions = [ActivityEvent.organization_id == organization_id]
        if user_id is not None:
            conditions.append(ActivityEvent.actor_user_id == user_id)
        result = await self.db.execute(
            select(ActivityEvent)
            .where(*conditions)
            .order_by(ActivityEvent.created_at.desc(), ActivityEvent.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def collection_outcome(self, job):
        """Record one terminal outcome per locked job, in the outcome transaction."""
        from app.models.project import Project
        from app.services.collection_lifecycle import TERMINAL_JOB_STATUSES
        if job.status not in TERMINAL_JOB_STATUSES:
            return
        event_id = uuid.uuid5(uuid.NAMESPACE_URL, f"socialscope:collection-outcome:{job.id}")
        if await self.db.get(ActivityEvent, event_id):
            return
        project = await self.db.get(Project, job.project_id)
        if not project:
            return
        self.db.add(ActivityEvent(
            id=event_id, organization_id=project.organization_id, project_id=project.id,
            actor_user_id=job.initiated_by, actor_label=job.initiator_label or "System / Unknown",
            action=f"collection_{job.status}", target_type="search_job",
            target_id=str(job.id), target_label=project.name,
            extra_metadata={"outcome": job.status, "mode": job.mode, "posts_collected": job.total_posts_collected},
        ))
        await self.db.flush()
