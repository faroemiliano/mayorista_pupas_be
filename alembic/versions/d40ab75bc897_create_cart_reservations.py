"""create cart reservations

Revision ID: d40ab75bc897
Revises: c39za64ab786
"""
from alembic import op
import sqlalchemy as sa

revision = "d40ab75bc897"
down_revision = "c39za64ab786"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reservas_carrito",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", sa.Integer(), sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("talle", sa.String(30), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("reservada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("usuario_id", "producto_id", "talle", name="uq_reserva_carrito_usuario_producto_talle"),
    )
    op.create_index("ix_reservas_carrito_usuario_id", "reservas_carrito", ["usuario_id"])
    op.create_index("ix_reservas_carrito_producto_id", "reservas_carrito", ["producto_id"])
    op.create_index("ix_reservas_carrito_expira_en", "reservas_carrito", ["expira_en"])


def downgrade():
    op.drop_table("reservas_carrito")
