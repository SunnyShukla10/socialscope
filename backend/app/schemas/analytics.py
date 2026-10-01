from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Any, Optional, Literal


class KPIOverview(BaseModel):
    total_posts: int
    unique_authors: int
    platforms_count: int
    top_hashtags: List[Dict[str, Any]]
    total_engagement: int


class VolumeDataPoint(BaseModel):
    date: str
    platform: str
    count: int


class VolumeResponse(BaseModel):
    data: List[VolumeDataPoint]
    platforms: List[str]


class PlatformDataPoint(BaseModel):
    platform: str
    post_count: int
    total_engagement: int


class PlatformResponse(BaseModel):
    data: List[PlatformDataPoint]


class WordMapNode(BaseModel):
    id: str
    label: str
    count: int
    value: int | None = None


class WordMapEdge(BaseModel):
    source: str
    target: str
    count: int
    weight: int | None = None


class WordMapResponse(BaseModel):
    nodes: List[WordMapNode]
    edges: List[WordMapEdge]


class AnalyticsSourceMixItem(BaseModel):
    platform: str
    post_count: int
    percentage: float


class AnalyticsTheme(BaseModel):
    name: str
    summary: str


class AnalyticsTopPosterSummary(BaseModel):
    account_id: str
    username: str
    platform: str
    post_count: int
    total_engagement: int
    summary: str
    topics: List[str] = Field(default_factory=list)
    discussion_style: str


class AnalyticsSummaryResponse(BaseModel):
    status: Literal["pending", "analyzed", "failed", "empty"]
    is_stale: bool = False
    total_posts: int
    sampled_posts: int
    source_mix: List[AnalyticsSourceMixItem]
    top_poster_share: float
    overview: Optional[str] = None
    themes: List[AnalyticsTheme] = Field(default_factory=list)
    top_posters: List[AnalyticsTopPosterSummary] = Field(default_factory=list)
    generated_at: Optional[datetime] = None
    model: Optional[str] = None
