"""create users and order owner

Revision ID: c72e8bd1a450
Revises: b3f48c2d91aa
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c72e8bd1a450"
down_revision: Union[str, Sequence[str], None] = "b3f48c2d91aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("google_sub", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("rol", sa.String(20), server_default="cliente", nullable=False),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("ultimo_acceso_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("google_sub"), sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_usuarios_id"), "usuarios", ["id"])
    op.create_index(op.f("ix_usuarios_google_sub"), "usuarios", ["google_sub"])
    op.create_index(op.f("ix_usuarios_email"), "usuarios", ["email"])
    op.create_index(op.f("ix_usuarios_rol"), "usuarios", ["rol"])
    op.add_column("pedidos", sa.Column("usuario_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_pedidos_usuario_id"), "pedidos", ["usuario_id"])
    op.create_foreign_key("fk_pedidos_usuario_id", "pedidos", "usuarios", ["usuario_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_pedidos_usuario_id", "pedidos", type_="foreignkey")
    op.drop_index(op.f("ix_pedidos_usuario_id"), table_name="pedidos")
    op.drop_column("pedidos", "usuario_id")
    op.drop_index(op.f("ix_usuarios_rol"), table_name="usuarios")
    op.drop_index(op.f("ix_usuarios_email"), table_name="usuarios")
    op.drop_index(op.f("ix_usuarios_google_sub"), table_name="usuarios")
    op.drop_index(op.f("ix_usuarios_id"), table_name="usuarios")
    op.drop_table("usuarios")
