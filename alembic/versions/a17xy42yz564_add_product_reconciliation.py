"""add product reconciliation state

Revision ID: a17xy42yz564
Revises: z06wx31xy453
"""
from alembic import op
import sqlalchemy as sa

revision = "a17xy42yz564"
down_revision = "z06wx31xy453"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("productos") as batch:
        batch.add_column(sa.Column("conciliacion_estado", sa.String(20), nullable=False, server_default="pendiente"))
        batch.add_column(sa.Column("conciliacion_criterio", sa.String(40), nullable=True))
        batch.add_column(sa.Column("conciliado_en", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_productos_conciliacion_estado", ["conciliacion_estado"])


def downgrade():
    with op.batch_alter_table("productos") as batch:
        batch.drop_index("ix_productos_conciliacion_estado")
        batch.drop_column("conciliado_en")
        batch.drop_column("conciliacion_criterio")
        batch.drop_column("conciliacion_estado")
