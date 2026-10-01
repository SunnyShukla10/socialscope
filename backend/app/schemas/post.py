from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime


class PostOut(BaseModel):
    excluded: bool = False
    id: uuid.UUID
    project_id: uuid.UUID
    search_job_id: Optional[uuid.UUID]
    account_id: Optional[uuid.UUID]
    platform: str
    vendor: str
    external_id: Optional[str]
    url: Optional[str]
    body: str
    author_username: Optional[str]
    author_display_name: Optional[str]
    author_followers: Optional[int]
    likes: int
    shares: int
    comments: int
    views: int
    engagement_score: float
    language: str
    hashtags: list
    mentions: list
    media_urls: list
    extra_metadata: dict
    published_at: Optional[datetime]
    collected_at: datetime

    model_config = {"from_attributes": True}


class PostListResponse(BaseModel):
    items: List[PostOut]
    total: int
    page: int
    per_page: int
    total_pages: int


class PostFilters(BaseModel):
    platform: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = None
    sort_by: str = "date"
    page: int = 1
    per_page: int = 25
