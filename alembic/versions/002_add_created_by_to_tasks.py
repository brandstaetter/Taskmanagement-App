"""Add created_by column to tasks

Revision ID: 002_add_created_by
Revises: 0996a25c0866
Create Date: 2026-03-15 00:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "002_add_created_by"
down_revision = "0996a25c0866"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guard: skip if the column already exists (e.g. on DBs migrated from 001_initial
    # which already created created_by as part of the initial schema).
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("tasks")]
    if "created_by" in existing_columns:
        return

    # Add created_by as nullable first so existing rows don't violate the constraint
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("created_by", sa.INTEGER(), nullable=True))

    # Default existing rows to user id=1 (the bootstrap admin)
    op.execute("UPDATE tasks SET created_by = 1 WHERE created_by IS NULL")

    # Enforce NOT NULL and add FK constraint + index (mirrors 001_initial schema)
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column("created_by", nullable=False)
        batch_op.create_foreign_key(
            "fk_tasks_created_by_users",
            "users",
            ["created_by"],
            ["id"],
        )

    # Add foreign key index (mirrors 001_initial)
    op.create_index("ix_tasks_created_by_fk", "tasks", ["created_by"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_columns = [col["name"] for col in inspector.get_columns("tasks")]
    if "created_by" not in existing_columns:
        return

    existing_indexes = [idx["name"] for idx in inspector.get_indexes("tasks")]
    if "ix_tasks_created_by_fk" in existing_indexes:
        op.drop_index("ix_tasks_created_by_fk", table_name="tasks")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_created_by_users", type_="foreignkey")
        batch_op.drop_column("created_by")
