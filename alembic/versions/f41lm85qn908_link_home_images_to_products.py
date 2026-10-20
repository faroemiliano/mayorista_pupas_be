"""link home images to products

Revision ID: f41lm85qn908
Revises: e30ki74pl897
"""

from alembic import op
import sqlalchemy as sa


revision = "f41lm85qn908"
down_revision = "e30ki74pl897"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "portadas_inicio",
        sa.Column(
            "producto_id",
            sa.Integer(),
            sa.ForeignKey("productos.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_portadas_inicio_producto_id", "portadas_inicio", ["producto_id"])


def downgrade():
    op.drop_index("ix_portadas_inicio_producto_id", table_name="portadas_inicio")
    op.drop_column("portadas_inicio", "producto_id")
