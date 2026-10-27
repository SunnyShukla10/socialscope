"""Private, organization-scoped feedback submitted from the application."""
import uuid
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("kind IN ('feedback', 'issue')", name="ck_feedback_kind"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitter_label: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    page_path: Mapped[str] = mapped_column(String(1000))
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
