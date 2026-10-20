"""create home hero images

Revision ID: e30ki74pl897
Revises: c29ab64bc786
"""

from alembic import op
import sqlalchemy as sa


revision = "e30ki74pl897"
down_revision = "c29ab64bc786"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portadas_inicio",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slide_id", sa.String(length=40), nullable=False, unique=True),
        sa.Column("imagen_url", sa.String(length=700), nullable=False),
        sa.Column("media_type", sa.String(length=50), nullable=False),
        sa.Column("actualizada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_portadas_inicio_slide_id", "portadas_inicio", ["slide_id"])


def downgrade():
    op.drop_index("ix_portadas_inicio_slide_id", table_name="portadas_inicio")
    op.drop_table("portadas_inicio")
