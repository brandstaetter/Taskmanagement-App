"""Add indexes.

Revision ID: 002
Revises: 001
Create Date: 2025-02-23 13:01:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f("ix_tasks_id"), "tasks", ["id"], unique=False)
    op.create_index(op.f("ix_tasks_title"), "tasks", ["title"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tasks_title"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_id"), table_name="tasks")
