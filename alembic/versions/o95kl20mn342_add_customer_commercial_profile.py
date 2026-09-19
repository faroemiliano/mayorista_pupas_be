"""add customer commercial profile

Revision ID: o95kl20mn342
Revises: n84jk19lm231
"""
from alembic import op
import sqlalchemy as sa


revision = "o95kl20mn342"
down_revision = "n84jk19lm231"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("provincia", sa.String(100), nullable=True))
    op.add_column("usuarios", sa.Column("localidad_partido", sa.String(150), nullable=True))
    op.add_column("usuarios", sa.Column("canal_venta", sa.String(30), nullable=True))
    op.add_column("usuarios", sa.Column("tienda_online_url", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("usuarios", "tienda_online_url")
    op.drop_column("usuarios", "canal_venta")
    op.drop_column("usuarios", "localidad_partido")
    op.drop_column("usuarios", "provincia")
