"""Research pulls, usage ledger, project deduplication and reversible exclusion.

Old migrations remain a historical bootstrap chain; recruitment tables are removed here.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
revision = "012"
down_revision = "011"
branch_labels = depends_on = None

def upgrade():
    op.create_table("collection_pulls",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("project_id", pg.UUID(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platforms", pg.JSONB(), nullable=False),
        sa.Column("comparison_limit", sa.Integer(), nullable=False),
        sa.Column("platform_limits", pg.JSONB(), nullable=False),
        sa.Column("request_limit", sa.Integer(), nullable=False),
        sa.Column("full_job_id", pg.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("comparison_limit BETWEEN 5 AND 8"),
        sa.CheckConstraint("request_limit BETWEEN 1 AND 100"))
    op.create_index("ix_collection_pulls_project_id", "collection_pulls", ["project_id"])
    op.add_column("search_jobs", sa.Column("pull_id", pg.UUID(), sa.ForeignKey("collection_pulls.id", ondelete="CASCADE")))
    op.add_column("search_jobs", sa.Column("mode", sa.String(20), nullable=False, server_default="collection"))
    op.add_column("search_jobs", sa.Column("fingerprint", sa.String(64), nullable=False, server_default=""))
    op.create_index("ix_search_jobs_pull_id", "search_jobs", ["pull_id"])
    op.add_column("normalized_posts", sa.Column("excluded", sa.Boolean(), nullable=False, server_default="false"))
    op.create_index("ix_normalized_posts_excluded", "normalized_posts", ["excluded"])
    op.create_table("run_posts",
        sa.Column("job_id", pg.UUID(), sa.ForeignKey("search_jobs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("post_id", pg.UUID(), sa.ForeignKey("normalized_posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("encountered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_run_posts_post_id", "run_posts", ["post_id"])
    op.execute("INSERT INTO run_posts(job_id,post_id,encountered_at) SELECT search_job_id,id,collected_at FROM normalized_posts WHERE search_job_id IS NOT NULL")
    # Retain earliest observed row, preserving all old run encounters.
    op.execute("CREATE TEMP TABLE post_merge ON COMMIT DROP AS SELECT id, first_value(id) OVER (PARTITION BY project_id,platform,external_id ORDER BY collected_at,id) AS keeper FROM normalized_posts WHERE external_id IS NOT NULL")
    op.execute("INSERT INTO run_posts(job_id,post_id,encountered_at) SELECT r.job_id,m.keeper,r.encountered_at FROM run_posts r JOIN post_merge m ON m.id=r.post_id WHERE m.id<>m.keeper ON CONFLICT DO NOTHING")
    op.execute("DELETE FROM normalized_posts WHERE id IN (SELECT id FROM post_merge WHERE id<>keeper)")
    op.drop_constraint("uq_normalized_post_job_platform_external_id", "normalized_posts", type_="unique")
    op.create_unique_constraint("uq_normalized_post_project_platform_external_id", "normalized_posts", ["project_id","platform","external_id"])
    op.create_table("provider_usage",
        sa.Column("id", pg.UUID(), primary_key=True),
        sa.Column("pull_id", pg.UUID(), sa.ForeignKey("collection_pulls.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", pg.UUID(), sa.ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("reserved", sa.Integer(), nullable=False),
        sa.Column("estimated", sa.Integer()), sa.Column("reported", sa.Integer()),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for col in ("pull_id", "job_id"):
        op.create_index("ix_provider_usage_"+col, "provider_usage", [col])
    op.create_table("provider_cache",
        sa.Column("pull_id", pg.UUID(), sa.ForeignKey("collection_pulls.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.drop_table("recruitment_flags")
    op.drop_table("recruitment_signal_analyses")
    op.drop_column("accounts", "is_flagged_for_recruitment")
    op.drop_column("accounts", "recruitment_notes")

def downgrade():
    raise RuntimeError("Research run membership cannot be losslessly downgraded. Restore a verified pre-migration backup.")
