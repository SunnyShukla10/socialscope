"""Remember custom post distributions for previews and collections."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision = "013"
down_revision = "012"
branch_labels = depends_on = None

def upgrade():
    op.add_column("search_jobs", sa.Column("platform_percentages", JSONB(), nullable=False, server_default=sa.text("'{}'")))

def downgrade():
    op.drop_column("search_jobs", "platform_percentages")
