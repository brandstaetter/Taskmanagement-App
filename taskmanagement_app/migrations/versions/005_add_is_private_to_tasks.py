"""Add is_private column to tasks

Revision ID: 005_add_is_private
Revises: 004_drop_assignment_columns
Create Date: 2026-03-22

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "005_add_is_private"
down_revision = "004_drop_assignment_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("tasks")]
    if "is_private" in existing_columns:
        return

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("is_private", sa.Boolean(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("tasks")]
    if "is_private" not in existing_columns:
        return

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("is_private")
