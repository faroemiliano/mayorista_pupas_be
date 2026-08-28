"""create dux sync status

Revision ID: j40fg75hi897
Revises: i39ef64gh786
"""
from alembic import op
import sqlalchemy as sa

revision = "j40fg75hi897"
down_revision = "i39ef64gh786"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sincronizaciones_dux",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recurso", sa.String(50), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("procesados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actualizados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_local", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("iniciada_en", sa.DateTime(timezone=True)),
        sa.Column("finalizada_en", sa.DateTime(timezone=True)),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sincronizaciones_dux_recurso", "sincronizaciones_dux", ["recurso"], unique=True)


def downgrade():
    op.drop_table("sincronizaciones_dux")
