"""Add private feedback, collection attribution, and account session revocation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "014"
down_revision = "013"
branch_labels = depends_on = None


def upgrade():
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("search_jobs", sa.Column("initiated_by", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_job_initiator", "search_jobs", "users", ["initiated_by"], ["id"], ondelete="SET NULL")
    op.add_column("search_jobs", sa.Column("initiator_label", sa.String(255), nullable=True))
    op.create_table(
        "feedback",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("submitter_label", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("page_path", sa.String(1000), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('feedback', 'issue')", name="ck_feedback_kind"),
    )
    op.create_index("ix_feedback_organization_id", "feedback", ["organization_id"])
    op.create_index("ix_activity_org_time", "activity_events", ["organization_id", "created_at"])
    op.create_index("ix_activity_org_actor_time", "activity_events", ["organization_id", "actor_user_id", "created_at"])


def downgrade():
    op.drop_index("ix_activity_org_actor_time", table_name="activity_events")
    op.drop_index("ix_activity_org_time", table_name="activity_events")
    op.drop_table("feedback")
    op.drop_column("search_jobs", "initiator_label")
    op.drop_constraint("fk_job_initiator", "search_jobs", type_="foreignkey")
    op.drop_column("search_jobs", "initiated_by")
    op.drop_column("users", "token_version")
