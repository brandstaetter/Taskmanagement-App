"""Add default values.

Revision ID: 003
Revises: 002
Create Date: 2025-02-23 13:01:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support modifying columns directly, so we need to:
    # 1. Create a new table with the desired schema
    # 2. Copy the data
    # 3. Drop the old table
    # 4. Rename the new table

    # Create new table
    op.create_table(
        "tasks_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("reward", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy data
    op.execute("INSERT INTO tasks_new SELECT * FROM tasks")

    # Drop old table and indexes
    op.drop_index(op.f("ix_tasks_title"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_id"), table_name="tasks")
    op.drop_table("tasks")

    # Rename new table
    op.rename_table("tasks_new", "tasks")

    # Recreate indexes
    op.create_index(op.f("ix_tasks_id"), "tasks", ["id"], unique=False)
    op.create_index(op.f("ix_tasks_title"), "tasks", ["title"], unique=False)


def downgrade() -> None:
    # SQLite doesn't support modifying columns directly, so we need to:
    # 1. Create a new table with the old schema
    # 2. Copy the data
    # 3. Drop the new table
    # 4. Rename the old table

    # Create old table
    op.create_table(
        "tasks_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("reward", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy data
    op.execute("INSERT INTO tasks_old SELECT * FROM tasks")

    # Drop new table and indexes
    op.drop_index(op.f("ix_tasks_title"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_id"), table_name="tasks")
    op.drop_table("tasks")

    # Rename old table
    op.rename_table("tasks_old", "tasks")

    # Recreate indexes
    op.create_index(op.f("ix_tasks_id"), "tasks", ["id"], unique=False)
    op.create_index(op.f("ix_tasks_title"), "tasks", ["title"], unique=False)
