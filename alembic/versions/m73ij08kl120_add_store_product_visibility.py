"""add store product visibility

Revision ID: m73ij08kl120
Revises: l62hi97jk019
"""
from alembic import op
import sqlalchemy as sa

revision="m73ij08kl120";down_revision="l62hi97jk019";branch_labels=None;depends_on=None
def upgrade():op.add_column("productos",sa.Column("visible_tienda",sa.Boolean(),nullable=False,server_default="true"))
def downgrade():op.drop_column("productos","visible_tienda")
