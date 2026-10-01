"""Account type classification fields.

Revision ID: 008
Revises: 007
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("accounts", sa.Column("account_label", sa.String(length=50), nullable=True))
    op.add_column(
        "accounts",
        sa.Column("account_label_confidence", sa.Float(), nullable=True),
    )
    op.add_column("accounts", sa.Column("account_label_reason", sa.Text(), nullable=True))
    op.add_column(
        "accounts",
        sa.Column("account_label_source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("account_label_model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("account_label_prompt_version", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("account_labeled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "account_label_confirmed_by_human",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "accounts",
        sa.Column("account_label_input_hash", sa.String(length=64), nullable=True),
    )


def downgrade():
    op.drop_column("accounts", "account_label_input_hash")
    op.drop_column("accounts", "account_label_confirmed_by_human")
    op.drop_column("accounts", "account_labeled_at")
    op.drop_column("accounts", "account_label_prompt_version")
    op.drop_column("accounts", "account_label_model")
    op.drop_column("accounts", "account_label_source")
    op.drop_column("accounts", "account_label_reason")
    op.drop_column("accounts", "account_label_confidence")
    op.drop_column("accounts", "account_label")
