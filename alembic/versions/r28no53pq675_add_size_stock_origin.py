"""add size stock origin

Revision ID: r28no53pq675
Revises: q17mn42op564
"""
from alembic import op
import sqlalchemy as sa

revision = "r28no53pq675"
down_revision = "q17mn42op564"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("stocks_talles_productos", sa.Column("origen", sa.String(20), nullable=False, server_default="manual"))

def downgrade():
    op.drop_column("stocks_talles_productos", "origen")
