from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AnalyticsSummary(Base):
    __tablename__ = "analytics_summaries"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_analytics_summary_project"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    total_posts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sampled_posts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_mix: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    top_poster_share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    overview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    themes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    top_posters: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project")
