"""create stock reservations

Revision ID: k51gh86ij908
Revises: j40fg75hi897
"""
from alembic import op
import sqlalchemy as sa


revision = "k51gh86ij908"
down_revision = "j40fg75hi897"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reservas_stock",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pedido_id", sa.Integer(), sa.ForeignKey("pedidos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(30), nullable=False, server_default="activa"),
        sa.Column("reservada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("liberada_en", sa.DateTime(timezone=True)),
        sa.Column("reconciliada_en", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("pedido_id", "producto_id", name="uq_reserva_pedido_producto"),
    )
    op.create_index("ix_reservas_stock_id", "reservas_stock", ["id"])
    op.create_index("ix_reservas_stock_pedido_id", "reservas_stock", ["pedido_id"])
    op.create_index("ix_reservas_stock_producto_id", "reservas_stock", ["producto_id"])
    op.create_index("ix_reservas_stock_estado", "reservas_stock", ["estado"])


def downgrade():
    op.drop_table("reservas_stock")
