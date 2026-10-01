"""Collection cancellation and progress metadata.

Revision ID: 009
Revises: 008
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "search_jobs",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "search_jobs",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "search_jobs",
        sa.Column("cancel_requested_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "search_jobs",
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_search_jobs_cancel_requested_by_users",
        "search_jobs",
        "users",
        ["cancel_requested_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.drop_constraint(
        "fk_search_jobs_cancel_requested_by_users",
        "search_jobs",
        type_="foreignkey",
    )
    op.drop_column("search_jobs", "last_progress_at")
    op.drop_column("search_jobs", "cancel_requested_by")
    op.drop_column("search_jobs", "cancelled_at")
    op.drop_column("search_jobs", "cancel_requested_at")
