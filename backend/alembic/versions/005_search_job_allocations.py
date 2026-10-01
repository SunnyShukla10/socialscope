"""Search job requested counts and platform allocations

Revision ID: 005
Revises: 004
Create Date: 2026-06-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "search_jobs",
        sa.Column("requested_post_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_jobs",
        sa.Column("platform_allocations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
    )
    op.execute(
        """
        UPDATE search_jobs
        SET requested_post_count = max_results_per_platform * jsonb_array_length(platforms)
        WHERE requested_post_count IS NULL
        """
    )
    op.alter_column("search_jobs", "requested_post_count", nullable=False)


def downgrade() -> None:
    op.drop_column("search_jobs", "platform_allocations")
    op.drop_column("search_jobs", "requested_post_count")
