from datetime import datetime, timezone
from typing import Any, Literal, Optional
import uuid

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator


class ActivityEventOut(BaseModel):
    id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    actor_user_id: Optional[uuid.UUID] = None
    actor_label: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    extra_metadata: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}


class ActivityCleanupSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    before: AwareDatetime
    user_id: uuid.UUID | None = None

    @field_validator("before")
    @classmethod
    def past_cutoff(cls, value: datetime) -> datetime:
        if value >= datetime.now(timezone.utc):
            raise ValueError("Choose a cutoff in the past")
        return value.astimezone(timezone.utc)


class ActivityCleanupRequest(ActivityCleanupSelection):
    confirmation: Literal["DELETE"]


class ActivityCleanupPreview(ActivityCleanupSelection):
    matching_count: int


class ActivityCleanupResult(BaseModel):
    deleted_count: int
