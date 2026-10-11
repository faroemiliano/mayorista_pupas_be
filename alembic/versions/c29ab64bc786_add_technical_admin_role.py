"""add technical admin role

Revision ID: c29ab64bc786
Revises: b18za53ab675
"""

from alembic import op


revision = "c29ab64bc786"
down_revision = "b18za53ab675"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE usuarios SET rol = 'admin_tecnico' WHERE lower(email) = 'farixio.tech@gmail.com'")


def downgrade():
    op.execute("UPDATE usuarios SET rol = 'admin' WHERE lower(email) = 'farixio.tech@gmail.com' AND rol = 'admin_tecnico'")
