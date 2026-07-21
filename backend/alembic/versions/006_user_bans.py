"""add user access bans

Revision ID: 006
Revises: 005
Create Date: 2026-07-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("banned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("banned_by", sa.String(), nullable=True))
    op.create_index("ix_users_is_banned", "users", ["is_banned"])
    op.alter_column("users", "is_banned", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_users_is_banned", table_name="users")
    op.drop_column("users", "banned_by")
    op.drop_column("users", "banned_at")
    op.drop_column("users", "is_banned")
