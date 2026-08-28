"""add user phone

Revision ID: e95ab20cd342
Revises: d84fa91bc231
"""
from alembic import op
import sqlalchemy as sa

revision="e95ab20cd342"
down_revision="d84fa91bc231"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("usuarios",sa.Column("telefono",sa.String(50),nullable=True))

def downgrade():
    op.drop_column("usuarios","telefono")
