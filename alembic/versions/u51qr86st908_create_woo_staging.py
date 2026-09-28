"""create WooCommerce staging

Revision ID: u51qr86st908
Revises: s39op64qr786
"""
from alembic import op
import sqlalchemy as sa

revision="u51qr86st908"
down_revision="s39op64qr786"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("migracion_woocommerce",
        sa.Column("id",sa.Integer(),primary_key=True),
        sa.Column("tipo",sa.String(30),nullable=False),
        sa.Column("id_externo",sa.String(100),nullable=False),
        sa.Column("checksum",sa.String(64),nullable=False),
        sa.Column("datos",sa.JSON(),nullable=False),
        sa.Column("importado_en",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column("actualizado_en",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint("tipo","id_externo",name="uq_migracion_woo_tipo_id"))
    op.create_index("ix_migracion_woocommerce_tipo","migracion_woocommerce",["tipo"])
    op.create_index("ix_migracion_woocommerce_id_externo","migracion_woocommerce",["id_externo"])

def downgrade():
    op.drop_table("migracion_woocommerce")
