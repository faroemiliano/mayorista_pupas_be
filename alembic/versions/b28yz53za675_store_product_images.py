"""store uploaded product images

Revision ID: b28yz53za675
Revises: a17xy42yz564
"""
from alembic import op
import sqlalchemy as sa

revision = "b28yz53za675"
down_revision = "a17xy42yz564"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("imagenes_productos") as batch:
        batch.add_column(sa.Column("contenido", sa.LargeBinary(), nullable=True))
        batch.add_column(sa.Column("media_type", sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table("imagenes_productos") as batch:
        batch.drop_column("media_type")
        batch.drop_column("contenido")
