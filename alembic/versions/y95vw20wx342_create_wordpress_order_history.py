"""create WordPress order history

Revision ID: y95vw20wx342
Revises: x84uv19vw231
"""
from alembic import op
import sqlalchemy as sa

revision = "y95vw20wx342"
down_revision = "x84uv19vw231"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pedidos_historicos_wordpress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wordpress_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(100), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("wordpress_customer_id", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(40), nullable=False),
        sa.Column("moneda", sa.String(10), server_default="ARS", nullable=False),
        sa.Column("total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("descuento_total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("envio_total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("impuesto_total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("metodo_pago", sa.String(100), nullable=True),
        sa.Column("titulo_pago", sa.String(200), nullable=True),
        sa.Column("facturacion", sa.JSON(), nullable=False),
        sa.Column("envio", sa.JSON(), nullable=False),
        sa.Column("creado_en_wordpress", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pagado_en_wordpress", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completado_en_wordpress", sa.DateTime(timezone=True), nullable=True),
        sa.Column("importado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    for columna, unica in (("wordpress_id", True), ("numero", False), ("usuario_id", False), ("wordpress_customer_id", False), ("estado", False), ("creado_en_wordpress", False)):
        op.create_index(f"ix_pedidos_historicos_wordpress_{columna}", "pedidos_historicos_wordpress", [columna], unique=unica)
    op.create_table(
        "pedidos_items_historicos_wordpress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pedido_id", sa.Integer(), sa.ForeignKey("pedidos_historicos_wordpress.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wordpress_id", sa.Integer(), nullable=False),
        sa.Column("wordpress_product_id", sa.Integer(), nullable=False),
        sa.Column("wordpress_variation_id", sa.Integer(), server_default="0", nullable=False),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("nombre", sa.String(250), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("cantidad", sa.Integer(), server_default="0", nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("impuesto_total", sa.Numeric(14, 2), server_default="0", nullable=False),
        sa.Column("precio_unitario", sa.Numeric(14, 2), nullable=True),
        sa.Column("metadatos", sa.JSON(), nullable=False),
        sa.UniqueConstraint("pedido_id", "wordpress_id", name="uq_pedido_historico_item_wordpress"),
    )
    for columna in ("pedido_id", "wordpress_product_id", "wordpress_variation_id", "producto_id"):
        op.create_index(f"ix_pedidos_items_historicos_wordpress_{columna}", "pedidos_items_historicos_wordpress", [columna])


def downgrade():
    op.drop_table("pedidos_items_historicos_wordpress")
    op.drop_table("pedidos_historicos_wordpress")
