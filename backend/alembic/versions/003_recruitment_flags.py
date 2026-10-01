"""Recruitment project flags

Revision ID: 003
Revises: 002
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recruitment_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("normalized_username", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("flagged_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("unflagged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "account_id", name="uq_recruitment_flag_project_account"),
    )
    op.create_index(
        "idx_recruitment_flags_project_account",
        "recruitment_flags",
        ["project_id", "account_id"],
    )
    op.create_index(
        "idx_recruitment_flags_identity",
        "recruitment_flags",
        ["platform", "normalized_username", "is_active"],
    )

    op.execute(
        """
        INSERT INTO recruitment_flags (
            id, project_id, account_id, platform, normalized_username, is_active, notes, flagged_at, created_at, updated_at
        )
        SELECT
            md5(project_accounts.project_id::text || accounts.id::text)::uuid,
            project_accounts.project_id,
            accounts.id,
            accounts.platform,
            lower(regexp_replace(trim(accounts.username), '^@+', '')),
            true,
            accounts.recruitment_notes,
            now(),
            now(),
            now()
        FROM accounts
        JOIN (
            SELECT DISTINCT project_id, account_id
            FROM normalized_posts
            WHERE account_id IS NOT NULL
        ) AS project_accounts ON project_accounts.account_id = accounts.id
        WHERE accounts.is_flagged_for_recruitment = true
        ON CONFLICT (project_id, account_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index("idx_recruitment_flags_identity", table_name="recruitment_flags")
    op.drop_index("idx_recruitment_flags_project_account", table_name="recruitment_flags")
    op.drop_table("recruitment_flags")
