"""Init config table

Revision ID: f2304c5669f5
Revises:
Create Date: 2020-07-11 18:49:45.398018

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision = 'f2304c5669f5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    if "syndicate_config" in tables:
        return
    op.create_table(
        "syndicate_config",
        sa.Column("id", sa.UnicodeText, primary_key=True),
        sa.Column("syndicate_url", sa.UnicodeText, unique=True),
        sa.Column("syndicate_api_key", sa.UnicodeText),
        sa.Column("syndicate_organization", sa.UnicodeText),
        sa.Column("syndicate_replicate_organization", sa.Boolean),
        sa.Column("syndicate_author", sa.UnicodeText),
        sa.Column("predicate", sa.UnicodeText),
        sa.Column("syndicate_field_id", sa.UnicodeText),
        sa.Column("syndicate_flag", sa.UnicodeText),
        sa.Column("syndicate_prefix", sa.UnicodeText),
    )


def downgrade():
    op.drop_table('syndicate_config')
