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

    async def latest(self, organization_id: uuid.UUID, limit: int = 100) -> list[ActivityEvent]:
        result = await self.db.execute(
            select(ActivityEvent)
            .where(ActivityEvent.organization_id == organization_id)
            .order_by(ActivityEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
