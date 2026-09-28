"""create WordPress user links

Revision ID: x84uv19vw231
Revises: w73tu08uv120
"""
from alembic import op
import sqlalchemy as sa

revision = "x84uv19vw231"
down_revision = "w73tu08uv120"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "usuarios_wordpress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("wordpress_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_original", sa.String(255), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usuarios_wordpress_wordpress_id", "usuarios_wordpress", ["wordpress_id"], unique=True)
    op.create_index("ix_usuarios_wordpress_usuario_id", "usuarios_wordpress", ["usuario_id"])
    op.create_index("ix_usuarios_wordpress_email_original", "usuarios_wordpress", ["email_original"])


def downgrade():
    op.drop_table("usuarios_wordpress")
