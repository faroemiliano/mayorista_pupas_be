"""add email password auth

Revision ID: d84fa91bc231
Revises: c72e8bd1a450
"""
from alembic import op
import sqlalchemy as sa

revision = "d84fa91bc231"
down_revision = "c72e8bd1a450"
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column("usuarios", "google_sub", existing_type=sa.String(255), nullable=True)
    op.add_column("usuarios", sa.Column("apellido", sa.String(200), server_default="", nullable=False))
    op.add_column("usuarios", sa.Column("password_hash", sa.String(500), nullable=True))
    op.add_column("usuarios", sa.Column("email_verificado", sa.Boolean(), server_default="false", nullable=False))

def downgrade():
    op.drop_column("usuarios", "email_verificado")
    op.drop_column("usuarios", "password_hash")
    op.drop_column("usuarios", "apellido")
    op.alter_column("usuarios", "google_sub", existing_type=sa.String(255), nullable=False)
