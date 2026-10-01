from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime
from app.schemas.search_job import SearchJobCreate


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    domain: str = "general"
    research_question: Optional[str] = None
    boolean_query: Optional[str] = None
    platforms: list[str] = []
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    max_results_per_platform: Optional[int] = None


class ProjectLaunchCreate(ProjectCreate):
    initial_job: SearchJobCreate


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    domain: Optional[str] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str]
    domain: str
    status: str
    created_at: datetime
    updated_at: datetime
    job_count: int = 0
    post_count: int = 0
    settings: dict = {}
    research_question: Optional[str] = None
    boolean_query: Optional[str] = None
    platforms: list[str] = []
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    max_results_per_platform: Optional[int] = None

    model_config = {"from_attributes": True}
