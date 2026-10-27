"""Private project ownership and optional pasted error details."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "015"
down_revision = "014"
branch_labels = depends_on = None


def upgrade():
    op.add_column("projects", sa.Column("owner_user_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_project_owner", "projects", "users", ["owner_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_projects_owner_user_id", "projects", ["owner_user_id"])
    # Attribute only unambiguous, same-organization creation events. Unknown legacy
    # projects remain unassigned and are accessible to organization admins only.
    op.execute(sa.text("""
        UPDATE projects AS p SET owner_user_id = creators.user_id
        FROM (
            SELECT a.project_id, MIN(a.actor_user_id::text)::uuid AS user_id
            FROM activity_events AS a
            JOIN users AS u ON u.id = a.actor_user_id
            JOIN projects AS original ON original.id = a.project_id
            WHERE a.action = 'project_created'
              AND u.organization_id = original.organization_id
              AND a.organization_id = original.organization_id
            GROUP BY a.project_id
            HAVING COUNT(DISTINCT a.actor_user_id) = 1
        ) AS creators
        WHERE p.id = creators.project_id
    """))
    op.add_column("feedback", sa.Column("error_details", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("feedback", "error_details")
    op.drop_index("ix_projects_owner_user_id", table_name="projects")
    op.drop_constraint("fk_project_owner", "projects", type_="foreignkey")
    op.drop_column("projects", "owner_user_id")
