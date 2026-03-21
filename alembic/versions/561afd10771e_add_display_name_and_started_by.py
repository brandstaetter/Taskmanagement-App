"""add_display_name_and_started_by

Revision ID: 561afd10771e
Revises: 002_add_created_by
Create Date: 2026-03-21 08:08:48.999601

"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

# revision identifiers, used by Alembic.
revision = "561afd10771e"
down_revision = "002_add_created_by"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Add display_name to users
    user_columns = [col["name"] for col in inspector.get_columns("users")]
    if "display_name" not in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("display_name", sa.String(), nullable=True))

    # Add started_by to tasks
    task_columns = [col["name"] for col in inspector.get_columns("tasks")]
    if "started_by" not in task_columns:
        with op.batch_alter_table("tasks") as batch_op:
            batch_op.add_column(sa.Column("started_by", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_tasks_started_by_users",
                "users",
                ["started_by"],
                ["id"],
            )

        op.create_index("ix_tasks_started_by", "tasks", ["started_by"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    task_columns = [col["name"] for col in inspector.get_columns("tasks")]
    if "started_by" in task_columns:
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("tasks")]
        if "ix_tasks_started_by" in existing_indexes:
            op.drop_index("ix_tasks_started_by", table_name="tasks")

        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("tasks")}
        with op.batch_alter_table("tasks") as batch_op:
            if "fk_tasks_started_by_users" in existing_fks:
                batch_op.drop_constraint(
                    "fk_tasks_started_by_users", type_="foreignkey"
                )
            batch_op.drop_column("started_by")

    user_columns = [col["name"] for col in inspector.get_columns("users")]
    if "display_name" in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.drop_column("display_name")
