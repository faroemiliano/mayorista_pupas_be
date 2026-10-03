"""track product image source

Revision ID: e51bc86de908
Revises: d40ab75bc897
"""
from alembic import op
import sqlalchemy as sa


revision = "e51bc86de908"
down_revision = "d40ab75bc897"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("imagenes_productos") as batch:
        batch.add_column(sa.Column("origen_url", sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table("imagenes_productos") as batch:
        batch.drop_column("origen_url")
