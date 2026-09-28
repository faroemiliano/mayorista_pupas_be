"""add password reset

Revision ID: t40pq75rs897
Revises: u51qr86st908
"""
from alembic import op
import sqlalchemy as sa

revision="t40pq75rs897"
down_revision="u51qr86st908"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("usuarios",sa.Column("reset_password_token_hash",sa.String(64),nullable=True))
    op.add_column("usuarios",sa.Column("reset_password_expira_en",sa.DateTime(timezone=True),nullable=True))
    op.create_index("ix_usuarios_reset_password_token_hash","usuarios",["reset_password_token_hash"])
    op.add_column("usuarios",sa.Column("requiere_migracion_password",sa.Boolean(),server_default="false",nullable=False))

def downgrade():
    op.drop_column("usuarios","requiere_migracion_password")
    op.drop_index("ix_usuarios_reset_password_token_hash",table_name="usuarios")
    op.drop_column("usuarios","reset_password_expira_en")
    op.drop_column("usuarios","reset_password_token_hash")
