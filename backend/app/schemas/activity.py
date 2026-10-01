from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel


class ActivityEventOut(BaseModel):
    id: uuid.UUID
    project_id: Optional[uuid.UUID] = None
    actor_label: str
    action: str
    target_type: str
    target_id: Optional[str] = None
    target_label: Optional[str] = None
    extra_metadata: dict[str, Any] = {}
    created_at: datetime

    model_config = {"from_attributes": True}
