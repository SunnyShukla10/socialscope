"""Durable pull allowance, request ledger, response cache and run membership."""
import uuid
from sqlalchemy import String, Integer, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class CollectionPull(Base):
    __tablename__ = "collection_pulls"
    __table_args__ = (CheckConstraint("comparison_limit BETWEEN 5 AND 8"), CheckConstraint("request_limit BETWEEN 1 AND 100"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    platforms: Mapped[list] = mapped_column(JSONB)
    comparison_limit: Mapped[int] = mapped_column(Integer, default=8)
    platform_limits: Mapped[dict] = mapped_column(JSONB)
    request_limit: Mapped[int] = mapped_column(Integer, default=20)
    full_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_pulls.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_jobs.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(50))
    endpoint: Mapped[str] = mapped_column(String(255))
    reserved: Mapped[int] = mapped_column(Integer)
    estimated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reported: Mapped[int | None] = mapped_column(Integer, nullable=True)
    state: Mapped[str] = mapped_column(String(30), default="reserved")
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderCache(Base):
    __tablename__ = "provider_cache"
    pull_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collection_pulls.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RunPost(Base):
    __tablename__ = "run_posts"
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("search_jobs.id", ondelete="CASCADE"), primary_key=True)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("normalized_posts.id", ondelete="CASCADE"), primary_key=True, index=True)
    encountered_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
