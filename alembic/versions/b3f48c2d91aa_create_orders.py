"""create orders

Revision ID: b3f48c2d91aa
Revises: 7aec4b4c1b96
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b3f48c2d91aa"
down_revision: Union[str, Sequence[str], None] = "7aec4b4c1b96"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pedidos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=False),
        sa.Column("estado", sa.String(length=30), server_default="pendiente", nullable=False),
        sa.Column("cliente_nombre", sa.String(length=150), nullable=False),
        sa.Column("cliente_telefono", sa.String(length=50), nullable=False),
        sa.Column("cliente_email", sa.String(length=200), nullable=True),
        sa.Column("provincia", sa.String(length=100), nullable=False),
        sa.Column("localidad", sa.String(length=100), nullable=False),
        sa.Column("direccion", sa.String(length=250), nullable=False),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column("cantidad_productos_diferentes", sa.Integer(), nullable=False),
        sa.Column("cantidad_unidades", sa.Integer(), nullable=False),
        sa.Column("aplica_precio_24_productos", sa.Boolean(), nullable=False),
        sa.Column("subtotal_sin_descuento", sa.Numeric(14, 2), nullable=False),
        sa.Column("descuento_aplicado", sa.Numeric(14, 2), nullable=False),
        sa.Column("total", sa.Numeric(14, 2), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pedidos_codigo"), "pedidos", ["codigo"], unique=True)
    op.create_index(op.f("ix_pedidos_creado_en"), "pedidos", ["creado_en"], unique=False)
    op.create_index(op.f("ix_pedidos_estado"), "pedidos", ["estado"], unique=False)
    op.create_index(op.f("ix_pedidos_id"), "pedidos", ["id"], unique=False)

    op.create_table(
        "pedidos_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("producto_id", sa.Integer(), nullable=True),
        sa.Column("dux_codigo", sa.String(length=100), nullable=False),
        sa.Column("producto_nombre", sa.String(length=200), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_mayorista", sa.Numeric(14, 2), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(14, 2), nullable=False),
        sa.Column("subtotal_sin_descuento", sa.Numeric(14, 2), nullable=False),
        sa.Column("descuento_aplicado", sa.Numeric(14, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pedidos_items_id"), "pedidos_items", ["id"], unique=False)
    op.create_index(op.f("ix_pedidos_items_pedido_id"), "pedidos_items", ["pedido_id"], unique=False)
    op.create_index(op.f("ix_pedidos_items_producto_id"), "pedidos_items", ["producto_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pedidos_items_producto_id"), table_name="pedidos_items")
    op.drop_index(op.f("ix_pedidos_items_pedido_id"), table_name="pedidos_items")
    op.drop_index(op.f("ix_pedidos_items_id"), table_name="pedidos_items")
    op.drop_table("pedidos_items")
    op.drop_index(op.f("ix_pedidos_id"), table_name="pedidos")
    op.drop_index(op.f("ix_pedidos_estado"), table_name="pedidos")
    op.drop_index(op.f("ix_pedidos_creado_en"), table_name="pedidos")
    op.drop_index(op.f("ix_pedidos_codigo"), table_name="pedidos")
    op.drop_table("pedidos")
