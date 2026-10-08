"""add product image backup url

Revision ID: a17xy42za564
Revises: z06wx31xy453
"""

from alembic import op
import sqlalchemy as sa


revision = "a17xy42za564"
down_revision = "z06wx31xy453"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("imagenes_productos") as batch:
        batch.add_column(sa.Column("respaldo_url", sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table("imagenes_productos") as batch:
        batch.drop_column("respaldo_url")
