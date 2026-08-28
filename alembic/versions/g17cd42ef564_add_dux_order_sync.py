"""add dux order sync

Revision ID: g17cd42ef564
Revises: f06bc31de453
"""
from alembic import op
import sqlalchemy as sa
revision="g17cd42ef564";down_revision="f06bc31de453";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("usuarios",sa.Column("dux_id_cliente",sa.Integer(),nullable=True));op.create_index(op.f("ix_usuarios_dux_id_cliente"),"usuarios",["dux_id_cliente"],unique=True)
    for name,type_ in [("dux_id_pedido",sa.Integer()),("dux_nro_pedido",sa.Integer()),("dux_id_personal",sa.Integer()),("estado_sync_dux",sa.String(30)),("error_sync_dux",sa.Text()),("sincronizado_dux_en",sa.DateTime(timezone=True))]:op.add_column("pedidos",sa.Column(name,type_,server_default="pendiente" if name=="estado_sync_dux" else None,nullable=False if name=="estado_sync_dux" else True))
    op.create_index(op.f("ix_pedidos_dux_id_pedido"),"pedidos",["dux_id_pedido"],unique=True);op.create_index(op.f("ix_pedidos_estado_sync_dux"),"pedidos",["estado_sync_dux"])
def downgrade():
    op.drop_index(op.f("ix_pedidos_estado_sync_dux"),table_name="pedidos");op.drop_index(op.f("ix_pedidos_dux_id_pedido"),table_name="pedidos")
    for name in ["sincronizado_dux_en","error_sync_dux","estado_sync_dux","dux_id_personal","dux_nro_pedido","dux_id_pedido"]:op.drop_column("pedidos",name)
    op.drop_index(op.f("ix_usuarios_dux_id_cliente"),table_name="usuarios");op.drop_column("usuarios","dux_id_cliente")
