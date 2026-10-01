"""Cached LLM analytics summaries.

Revision ID: 011
Revises: 010
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analytics_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("input_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("model", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("prompt_version", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("total_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sampled_posts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_mix", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("top_poster_share", sa.Float(), nullable=False, server_default="0"),
        sa.Column("overview", sa.Text(), nullable=True),
        sa.Column("themes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("top_posters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_analytics_summary_project"),
    )
    op.create_index("idx_analytics_summaries_status", "analytics_summaries", ["status"])


def downgrade():
    op.drop_index("idx_analytics_summaries_status", table_name="analytics_summaries")
    op.drop_table("analytics_summaries")
