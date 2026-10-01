from sqlalchemy import String, Text, DateTime, func, ForeignKey, Integer, Float, Boolean
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from typing import Optional
from app.models.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=True)
    bio: Mapped[str] = mapped_column(Text, nullable=True)
    followers: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    following: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    profile_url: Mapped[str] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    avg_engagement_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extra_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    account_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_label_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    account_label_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    account_label_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_label_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_label_prompt_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    account_labeled_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    account_label_confirmed_by_human: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    account_label_input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    account_enrichment_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
    )
    account_enrichment_queued_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    account_enrichment_started_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    account_enrichment_completed_at: Mapped[Optional[DateTime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    account_enrichment_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    posts: Mapped[list["NormalizedPost"]] = relationship("NormalizedPost", back_populates="account")
    platform_profiles: Mapped[list["AccountPlatformProfile"]] = relationship(
        "AccountPlatformProfile", back_populates="account"
    )


class AccountPlatformProfile(Base):
    __tablename__ = "account_platform_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(255), nullable=True)
    username: Mapped[str] = mapped_column(String(255), nullable=True)
    profile_url: Mapped[str] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="platform_profiles")
