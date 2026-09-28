"""add WordPress user trace

Revision ID: w73tu08uv120
Revises: v62st97tu019
"""
from alembic import op
import sqlalchemy as sa

revision = "w73tu08uv120"
down_revision = "v62st97tu019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("wordpress_id", sa.Integer(), nullable=True))
    op.create_index("ix_usuarios_wordpress_id", "usuarios", ["wordpress_id"], unique=True)
    op.add_column("usuarios", sa.Column("origen", sa.String(20), server_default="web", nullable=False))
    op.create_index("ix_usuarios_origen", "usuarios", ["origen"])


def downgrade():
    op.drop_index("ix_usuarios_origen", table_name="usuarios")
    op.drop_column("usuarios", "origen")
    op.drop_index("ix_usuarios_wordpress_id", table_name="usuarios")
    op.drop_column("usuarios", "wordpress_id")
