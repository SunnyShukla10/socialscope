from sqlalchemy import String, Text, DateTime, func, ForeignKey, Integer
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from app.models.base import Base


class SearchJob(Base):
    __tablename__ = "search_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    platforms: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    date_from: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    date_to: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    max_results_per_platform: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    requested_post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    platform_allocations: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    platform_states: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    total_posts_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_progress_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pull_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_pulls.id", ondelete="CASCADE"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="collection")
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="search_jobs")
    query_versions: Mapped[list["QueryVersion"]] = relationship(
        "QueryVersion", back_populates="search_job"
    )
    posts: Mapped[list["NormalizedPost"]] = relationship("NormalizedPost", back_populates="search_job")
