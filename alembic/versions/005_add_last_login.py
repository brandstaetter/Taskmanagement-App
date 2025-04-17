"""Add last_login field to users table

Revision ID: 005_add_last_login
Revises: 004_create_users_table
Create Date: 2025-04-16 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004_create_users_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add last_login column to users table."""
    op.add_column(
        "users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    """Remove last_login column from users table."""
    op.drop_column("users", "last_login")
