"""create dux clients

Revision ID: i39ef64gh786
Revises: h28de53fg675
"""
from alembic import op
import sqlalchemy as sa

revision = "i39ef64gh786"
down_revision = "h28de53fg675"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "clientes_dux",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dux_id_cliente", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(100)), sa.Column("nombre", sa.String(250), nullable=False),
        sa.Column("email", sa.String(255)), sa.Column("telefono", sa.String(100)),
        sa.Column("tipo_doc", sa.String(30)), sa.Column("nro_doc", sa.String(30)),
        sa.Column("cuit_cuil", sa.String(30)), sa.Column("domicilio", sa.String(300)),
        sa.Column("localidad", sa.String(150)), sa.Column("provincia", sa.String(150)),
        sa.Column("habilitado", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("presente_en_dux", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("fecha_creacion_dux", sa.DateTime(timezone=True)),
        sa.Column("sincronizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for name, column, unique in [
        ("dux_id_cliente", "dux_id_cliente", True), ("nombre", "nombre", False),
        ("email", "email", False), ("nro_doc", "nro_doc", False),
        ("cuit_cuil", "cuit_cuil", False), ("presente_en_dux", "presente_en_dux", False),
    ]:
        op.create_index(f"ix_clientes_dux_{name}", "clientes_dux", [column], unique=unique)


def downgrade():
    op.drop_table("clientes_dux")
