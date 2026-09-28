"""add WordPress catalog trace

Revision ID: v62st97tu019
Revises: t40pq75rs897
"""
from alembic import op
import sqlalchemy as sa

revision = "v62st97tu019"
down_revision = "t40pq75rs897"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("categorias", sa.Column("wordpress_id", sa.Integer(), nullable=True))
    op.create_index("ix_categorias_wordpress_id", "categorias", ["wordpress_id"], unique=True)
    op.add_column("subcategorias", sa.Column("wordpress_id", sa.Integer(), nullable=True))
    op.create_index("ix_subcategorias_wordpress_id", "subcategorias", ["wordpress_id"], unique=True)
    op.add_column("productos", sa.Column("wordpress_id", sa.Integer(), nullable=True))
    op.create_index("ix_productos_wordpress_id", "productos", ["wordpress_id"], unique=True)
    op.add_column("productos", sa.Column("origen", sa.String(20), server_default="dux", nullable=False))
    op.create_index("ix_productos_origen", "productos", ["origen"])
    op.create_table(
        "variaciones_productos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("wordpress_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("atributos", sa.JSON(), nullable=False),
        sa.Column("precio", sa.Numeric(12, 2), nullable=True),
        sa.Column("stock", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estado_stock", sa.String(30), nullable=True),
        sa.Column("habilitada", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_variaciones_productos_producto_id", "variaciones_productos", ["producto_id"])
    op.create_index("ix_variaciones_productos_wordpress_id", "variaciones_productos", ["wordpress_id"], unique=True)
    op.create_index("ix_variaciones_productos_sku", "variaciones_productos", ["sku"])


def downgrade():
    op.drop_table("variaciones_productos")
    op.drop_index("ix_productos_origen", table_name="productos")
    op.drop_column("productos", "origen")
    op.drop_index("ix_productos_wordpress_id", table_name="productos")
    op.drop_column("productos", "wordpress_id")
    op.drop_index("ix_subcategorias_wordpress_id", table_name="subcategorias")
    op.drop_column("subcategorias", "wordpress_id")
    op.drop_index("ix_categorias_wordpress_id", table_name="categorias")
    op.drop_column("categorias", "wordpress_id")
