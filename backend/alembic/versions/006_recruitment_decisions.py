"""Recruitment decisions

Revision ID: 006
Revises: 005
Create Date: 2026-06-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recruitment_flags",
        sa.Column("decision", sa.String(length=20), nullable=False, server_default="flagged"),
    )
    op.create_check_constraint(
        "ck_recruitment_flags_decision",
        "recruitment_flags",
        "decision IN ('flagged', 'suppressed')",
    )
    op.create_index(
        "idx_recruitment_flags_identity_decision",
        "recruitment_flags",
        ["platform", "normalized_username", "decision", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("idx_recruitment_flags_identity_decision", table_name="recruitment_flags")
    op.drop_constraint("ck_recruitment_flags_decision", "recruitment_flags", type_="check")
    op.drop_column("recruitment_flags", "decision")
