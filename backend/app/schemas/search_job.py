from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional, List
import uuid
from datetime import datetime, timezone

MIN_REQUESTED_POST_COUNT = 100
MAX_RESULTS_PER_PLATFORM = 5000
JobStatus = Literal[
    "pending",
    "queued",
    "running",
    "cancelling",
    "completed",
    "completed_with_errors",
    "cancelled",
    "failed",
]
PlatformStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "cancel_requested",
    "cancelled",
]


class SearchJobCreate(BaseModel):
    pull_id: Optional[uuid.UUID] = None
    mode: Literal["preview", "collection"] = "collection"
    comparison_limit: int = Field(default=8, ge=5, le=8)
    primary_credit_limit: int = Field(default=20, ge=1, le=100)
    request_limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_configuration(self):
        self.platforms = list(dict.fromkeys("twitter" if p.lower() == "x" else p.lower() for p in self.platforms))
        allowed = {"twitter", "reddit", "youtube", "instagram", "tiktok", "facebook"}
        if not self.platforms or any(p not in allowed for p in self.platforms):
            raise ValueError("Select at least one supported source")
        for key in ("date_from", "date_to"):
            value = getattr(self, key)
            if value and value.tzinfo is None:
                setattr(self, key, value.replace(tzinfo=timezone.utc))
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Start date must be on or before end date")
        return self

    name: str = Field(min_length=1, max_length=255)
    platforms: List[str]
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    query: str
    requested_post_count: Optional[int] = Field(
        default=None,
        ge=MIN_REQUESTED_POST_COUNT,
        le=MAX_RESULTS_PER_PLATFORM,
    )
    max_results_per_platform: int = Field(
        default=500,
        ge=MIN_REQUESTED_POST_COUNT,
        le=MAX_RESULTS_PER_PLATFORM,
    )


class QueryVersionOut(BaseModel):
    id: uuid.UUID
    version_number: int
    label: str
    boolean_query: str
    description: Optional[str]
    or_groups: list
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PlatformCollectionStateOut(BaseModel):
    status: PlatformStatus
    posts_collected: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_progress_at: Optional[datetime] = None
    error: Optional[str] = None
    provider_stop_reason: Optional[str] = None
    provider_stop_details: Optional[dict] = None


class SearchJobOut(BaseModel):
    pull_id: Optional[uuid.UUID] = None
    mode: str = "collection"
    usage: dict = Field(default_factory=dict)
    preview_examples: list[dict] = Field(default_factory=list)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    status: JobStatus
    platforms: list
    date_from: Optional[datetime]
    date_to: Optional[datetime]
    max_results_per_platform: int
    requested_post_count: int
    platform_allocations: dict[str, int] = Field(default_factory=dict)
    platform_states: dict[str, PlatformCollectionStateOut] = Field(default_factory=dict)
    total_posts_collected: int
    error_message: Optional[str]
    celery_task_id: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancel_requested_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancel_requested_by: Optional[uuid.UUID]
    last_progress_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    query_versions: List[QueryVersionOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SearchJobCancellationOut(BaseModel):
    job_id: uuid.UUID
    status: Literal["cancelling"]
    cancel_requested_at: datetime
    cancel_requested_by: uuid.UUID
    completed_platforms: list[str] = Field(default_factory=list)
    cancelling_platforms: list[str] = Field(default_factory=list)
