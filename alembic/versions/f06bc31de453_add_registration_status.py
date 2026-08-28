"""add registration status

Revision ID: f06bc31de453
Revises: e95ab20cd342
"""
from alembic import op
import sqlalchemy as sa

revision="f06bc31de453"
down_revision="e95ab20cd342"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("usuarios",sa.Column("estado_registro",sa.String(20),server_default="pendiente",nullable=False))
    op.create_index(op.f("ix_usuarios_estado_registro"),"usuarios",["estado_registro"])
    op.execute("UPDATE usuarios SET estado_registro = 'aprobado' WHERE rol = 'admin'")

def downgrade():
    op.drop_index(op.f("ix_usuarios_estado_registro"),table_name="usuarios")
    op.drop_column("usuarios","estado_registro")
