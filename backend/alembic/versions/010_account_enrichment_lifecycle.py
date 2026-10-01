"""Account enrichment lifecycle fields.

Revision ID: 010
Revises: 009
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "accounts",
        sa.Column(
            "account_enrichment_status",
            sa.String(length=50),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "accounts",
        sa.Column("account_enrichment_queued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("account_enrichment_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("account_enrichment_completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column("account_enrichment_error", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE accounts
        SET account_enrichment_status = 'completed',
            account_enrichment_completed_at = COALESCE(
                account_labeled_at,
                updated_at,
                CURRENT_TIMESTAMP
            )
        WHERE account_label IS NOT NULL
           OR account_label_confirmed_by_human = true
        """
    )
    op.create_index(
        "idx_accounts_enrichment_status",
        "accounts",
        ["account_enrichment_status"],
    )


def downgrade():
    op.drop_index("idx_accounts_enrichment_status", table_name="accounts")
    op.drop_column("accounts", "account_enrichment_error")
    op.drop_column("accounts", "account_enrichment_completed_at")
    op.drop_column("accounts", "account_enrichment_started_at")
    op.drop_column("accounts", "account_enrichment_queued_at")
    op.drop_column("accounts", "account_enrichment_status")
