"""create notifications

Revision ID: l62hi97jk019
Revises: k51gh86ij908
"""
from alembic import op
import sqlalchemy as sa

revision="l62hi97jk019";down_revision="k51gh86ij908";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("notificaciones",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("usuario_id",sa.Integer(),sa.ForeignKey("usuarios.id",ondelete="CASCADE")),
        sa.Column("pedido_id",sa.Integer(),sa.ForeignKey("pedidos.id",ondelete="CASCADE")),
        sa.Column("audiencia",sa.String(20),nullable=False),sa.Column("tipo",sa.String(50),nullable=False),
        sa.Column("titulo",sa.String(200),nullable=False),sa.Column("mensaje",sa.Text(),nullable=False),
        sa.Column("leida",sa.Boolean(),nullable=False,server_default="false"),
        sa.Column("email_destino",sa.String(255)),sa.Column("email_estado",sa.String(20),nullable=False,server_default="no_configurado"),
        sa.Column("email_error",sa.Text()),sa.Column("creada_en",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    for column in ("usuario_id","pedido_id","audiencia","leida","creada_en"):
        op.create_index(f"ix_notificaciones_{column}","notificaciones",[column])

def downgrade():op.drop_table("notificaciones")
