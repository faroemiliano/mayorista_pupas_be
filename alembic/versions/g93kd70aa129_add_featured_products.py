"""add featured products

Revision ID: g93kd70aa129
Revises: e51bc86de908
"""
from alembic import op
import sqlalchemy as sa

revision = "g93kd70aa129"
down_revision = "e51bc86de908"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("productos") as batch:
        batch.add_column(sa.Column("destacado", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("orden_destacado", sa.Integer(), nullable=True))
        batch.create_index("ix_productos_destacado", ["destacado"])

def downgrade():
    with op.batch_alter_table("productos") as batch:
        batch.drop_index("ix_productos_destacado")
        batch.drop_column("orden_destacado")
        batch.drop_column("destacado")
