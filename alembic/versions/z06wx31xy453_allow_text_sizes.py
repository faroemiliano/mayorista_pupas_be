"""allow text sizes

Revision ID: z06wx31xy453
Revises: y95vw20wx342
"""
from alembic import op
import sqlalchemy as sa

revision = "z06wx31xy453"
down_revision = "y95vw20wx342"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stocks_talles_productos") as batch:
        batch.drop_constraint("ck_stock_talle_1_5", type_="check")
        batch.alter_column("talle", existing_type=sa.Integer(), type_=sa.String(30), existing_nullable=False, postgresql_using="talle::text")
    with op.batch_alter_table("pedidos_items") as batch:
        batch.alter_column("talle", existing_type=sa.Integer(), type_=sa.String(30), existing_nullable=True, postgresql_using="talle::text")
    with op.batch_alter_table("reservas_stock") as batch:
        batch.alter_column("talle", existing_type=sa.Integer(), type_=sa.String(30), existing_nullable=True, postgresql_using="talle::text")


def downgrade():
    with op.batch_alter_table("reservas_stock") as batch:
        batch.alter_column("talle", existing_type=sa.String(30), type_=sa.Integer(), existing_nullable=True, postgresql_using="talle::integer")
    with op.batch_alter_table("pedidos_items") as batch:
        batch.alter_column("talle", existing_type=sa.String(30), type_=sa.Integer(), existing_nullable=True, postgresql_using="talle::integer")
    with op.batch_alter_table("stocks_talles_productos") as batch:
        batch.alter_column("talle", existing_type=sa.String(30), type_=sa.Integer(), existing_nullable=False, postgresql_using="talle::integer")
        batch.create_check_constraint("ck_stock_talle_1_5", "talle BETWEEN 1 AND 5")
