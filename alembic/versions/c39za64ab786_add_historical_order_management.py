"""add historical order management status

Revision ID: c39za64ab786
Revises: b28yz53za675
"""
from alembic import op
import sqlalchemy as sa

revision = "c39za64ab786"
down_revision = "b28yz53za675"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("pedidos_historicos_wordpress") as batch:
        batch.add_column(sa.Column("estado_gestion", sa.String(length=40), nullable=True))
        batch.create_index("ix_pedidos_historicos_wordpress_estado_gestion", ["estado_gestion"])


def downgrade():
    with op.batch_alter_table("pedidos_historicos_wordpress") as batch:
        batch.drop_index("ix_pedidos_historicos_wordpress_estado_gestion")
        batch.drop_column("estado_gestion")
