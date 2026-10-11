"""create customer reviews

Revision ID: b18za53ab675
Revises: a17xy42za564
"""

from alembic import op
import sqlalchemy as sa


revision = "b18za53ab675"
down_revision = "a17xy42za564"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resenas_clientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=True),
        sa.Column("apellido", sa.String(length=100), nullable=True),
        sa.Column("calificacion", sa.Integer(), nullable=False),
        sa.Column("comentario", sa.Text(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("destacada", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("calificacion >= 1 AND calificacion <= 5", name="ck_resenas_clientes_calificacion"),
        sa.CheckConstraint("estado IN ('pendiente', 'aprobada', 'rechazada')", name="ck_resenas_clientes_estado"),
        sa.UniqueConstraint("usuario_id", name="uq_resenas_clientes_usuario_id"),
    )
    for column in ("usuario_id", "estado", "destacada", "creada_en"):
        op.create_index(f"ix_resenas_clientes_{column}", "resenas_clientes", [column])


def downgrade():
    op.drop_table("resenas_clientes")
