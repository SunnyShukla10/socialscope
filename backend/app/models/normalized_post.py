from sqlalchemy import String, Text, DateTime, func, ForeignKey, Integer, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from app.models.base import Base


class NormalizedPost(Base):
    __tablename__ = "normalized_posts"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "platform",
            "external_id",
            name="uq_normalized_post_project_platform_external_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    search_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_jobs.id", ondelete="SET NULL"), nullable=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    author_username: Mapped[str] = mapped_column(String(255), nullable=True)
    author_display_name: Mapped[str] = mapped_column(String(255), nullable=True)
    author_followers: Mapped[int] = mapped_column(Integer, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shares: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engagement_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sentiment: Mapped[str] = mapped_column(String(50), nullable=False, default="neutral")
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    hashtags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    mentions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    media_urls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    published_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="posts")
    search_job: Mapped["SearchJob"] = relationship("SearchJob", back_populates="posts")
    account: Mapped["Account"] = relationship("Account", back_populates="posts")
    post_tags: Mapped[list["PostTag"]] = relationship("PostTag", back_populates="post")
