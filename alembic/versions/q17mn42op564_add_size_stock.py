"""add size stock

Revision ID: q17mn42op564
Revises: p06lm31no453
"""
from alembic import op
import sqlalchemy as sa

revision = "q17mn42op564"
down_revision = "p06lm31no453"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("stocks_talles_productos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("talle", sa.Integer(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("producto_id", "talle", name="uq_stock_talle_producto"),
        sa.CheckConstraint("talle BETWEEN 1 AND 5", name="ck_stock_talle_1_5"),
        sa.CheckConstraint("cantidad >= 0", name="ck_stock_talle_no_negativo"),
    )
    op.create_index("ix_stocks_talles_productos_producto_id", "stocks_talles_productos", ["producto_id"])
    op.add_column("pedidos_items", sa.Column("talle", sa.Integer(), nullable=True))
    op.drop_constraint("uq_reserva_pedido_producto", "reservas_stock", type_="unique")
    op.add_column("reservas_stock", sa.Column("talle", sa.Integer(), nullable=True))
    op.create_unique_constraint("uq_reserva_pedido_producto_talle", "reservas_stock", ["pedido_id", "producto_id", "talle"])

def downgrade():
    op.drop_constraint("uq_reserva_pedido_producto_talle", "reservas_stock", type_="unique")
    op.drop_column("reservas_stock", "talle")
    op.create_unique_constraint("uq_reserva_pedido_producto", "reservas_stock", ["pedido_id", "producto_id"])
    op.drop_column("pedidos_items", "talle")
    op.drop_index("ix_stocks_talles_productos_producto_id", table_name="stocks_talles_productos")
    op.drop_table("stocks_talles_productos")
