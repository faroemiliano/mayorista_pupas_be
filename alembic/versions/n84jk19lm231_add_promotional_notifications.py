"""add promotional notifications

Revision ID: n84jk19lm231
Revises: m73ij08kl120
"""
from alembic import op
import sqlalchemy as sa


revision = "n84jk19lm231"
down_revision = "m73ij08kl120"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column("acepta_promociones_email", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("notificaciones", sa.Column("enlace_url", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("notificaciones", "enlace_url")
    op.drop_column("usuarios", "acepta_promociones_email")
