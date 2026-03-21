"""remove assignment_type and assigned_to columns

Migrate assigned_to FK data into the task_assigned_users M2M table,
then drop assignment_type enum column and assigned_to FK column.

Revision ID: 003_remove_assignment
Revises: 561afd10771e
Create Date: 2026-03-21

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision = "003_remove_assignment"
down_revision = "561afd10771e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    task_columns = [col["name"] for col in inspector.get_columns("tasks")]

    # Step 1: Migrate assigned_to data into task_assigned_users M2M table.
    # For rows with assignment_type='one' and a non-null assigned_to,
    # insert into the M2M table if not already present.
    if "assigned_to" in task_columns:
        bind.execute(text("""
                INSERT OR IGNORE INTO task_assigned_users (task_id, user_id)
                SELECT id, assigned_to FROM tasks
                WHERE assigned_to IS NOT NULL
                """))

    # Step 2: Drop assignment_type and assigned_to columns
    columns_to_drop = []
    if "assignment_type" in task_columns:
        columns_to_drop.append("assignment_type")
    if "assigned_to" in task_columns:
        columns_to_drop.append("assigned_to")

    if columns_to_drop:
        # Drop index on assigned_to if it exists
        existing_indexes = [idx["name"] for idx in inspector.get_indexes("tasks")]
        if "ix_tasks_assigned_to" in existing_indexes:
            op.drop_index("ix_tasks_assigned_to", table_name="tasks")

        # Drop FK and columns using batch mode (required for SQLite)
        existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("tasks")}
        with op.batch_alter_table("tasks") as batch_op:
            # Drop FK on assigned_to if it exists
            for fk_name in existing_fks:
                if fk_name and "assigned_to" in fk_name:
                    batch_op.drop_constraint(fk_name, type_="foreignkey")

            for col in columns_to_drop:
                batch_op.drop_column(col)


def downgrade() -> None:
    # Re-add the columns
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "assignment_type",
                sa.String(),
                nullable=False,
                server_default="any",
            )
        )
        batch_op.add_column(sa.Column("assigned_to", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_assigned_to_users",
            "users",
            ["assigned_to"],
            ["id"],
        )

    op.create_index("ix_tasks_assigned_to", "tasks", ["assigned_to"], unique=False)
