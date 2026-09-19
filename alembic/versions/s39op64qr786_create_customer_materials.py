"""create customer materials

Revision ID: s39op64qr786
Revises: r28no53pq675
"""
from alembic import op
import sqlalchemy as sa


revision = "s39op64qr786"
down_revision = "r28no53pq675"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "materiales_clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(160), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("nombre_archivo", sa.String(255), nullable=False),
        sa.Column("tipo_contenido", sa.String(50), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_materiales_clientes_creado_en", "materiales_clientes", ["creado_en"])


def downgrade():
    op.drop_index("ix_materiales_clientes_creado_en", table_name="materiales_clientes")
    op.drop_table("materiales_clientes")
