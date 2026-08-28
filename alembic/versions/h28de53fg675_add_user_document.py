"""add user document

Revision ID: h28de53fg675
Revises: g17cd42ef564
"""
from alembic import op
import sqlalchemy as sa
revision="h28de53fg675";down_revision="g17cd42ef564";branch_labels=None;depends_on=None
def upgrade():
    op.add_column("usuarios",sa.Column("documento",sa.String(20),nullable=True))
    op.create_index(op.f("ix_usuarios_documento"),"usuarios",["documento"],unique=True)
def downgrade():
    op.drop_index(op.f("ix_usuarios_documento"),table_name="usuarios");op.drop_column("usuarios","documento")
