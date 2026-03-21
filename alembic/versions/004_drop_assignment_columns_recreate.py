"""drop assignment_type and assigned_to columns via table recreate

Hotfix for migration 003 which may have silently failed on SQLite versions
that do not support ALTER TABLE DROP COLUMN (< 3.35.0). This migration uses
recreate="always" to force the safe copy-and-rename strategy that works on
all SQLite versions.

Revision ID: 004_drop_assignment_columns
Revises: 003_remove_assignment
Create Date: 2026-03-21

"""

from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "004_drop_assignment_columns"
down_revision = "003_remove_assignment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    task_columns = [col["name"] for col in inspector.get_columns("tasks")]

    cols_to_drop = [c for c in ("assignment_type", "assigned_to") if c in task_columns]
    if not cols_to_drop:
        return  # already gone, nothing to do

    # Drop index before recreating the table
    existing_indexes = [idx["name"] for idx in inspector.get_indexes("tasks")]
    if "ix_tasks_assigned_to" in existing_indexes:
        op.drop_index("ix_tasks_assigned_to", table_name="tasks")

    # recreate="always" forces Alembic to build a new table and copy data,
    # which works on every SQLite version (no ALTER TABLE DROP COLUMN needed).
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        for col in cols_to_drop:
            batch_op.drop_column(col)


def downgrade() -> None:
    pass  # not worth reversing a hotfix
