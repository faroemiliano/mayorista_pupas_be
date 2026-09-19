"""add customer address

Revision ID: p06lm31no453
Revises: o95kl20mn342
"""
from alembic import op
import sqlalchemy as sa


revision = "p06lm31no453"
down_revision = "o95kl20mn342"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("domicilio", sa.String(250), nullable=True))


def downgrade():
    op.drop_column("usuarios", "domicilio")
