"""Concurrent collection state and idempotent post writes.

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "search_jobs",
        sa.Column(
            "platform_states",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_unique_constraint(
        "uq_normalized_post_job_platform_external_id",
        "normalized_posts",
        ["search_job_id", "platform", "external_id"],
    )


def downgrade():
    op.drop_constraint(
        "uq_normalized_post_job_platform_external_id",
        "normalized_posts",
        type_="unique",
    )
    op.drop_column("search_jobs", "platform_states")
