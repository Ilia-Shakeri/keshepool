"""add durable USDT rate override history

Revision ID: 009
Revises: 008
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usdt_rate_override",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("changed_by_telegram_id", sa.String(length=20), nullable=True),
        sa.Column("change_source", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_usdt_rate_override_singleton"),
        sa.CheckConstraint("version > 0", name="ck_usdt_rate_override_version"),
        sa.CheckConstraint(
            "(is_active AND rate IS NOT NULL AND rate > 0) "
            "OR (NOT is_active AND rate IS NULL)",
            name="ck_usdt_rate_override_state",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "usdt_rate_override_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rate", sa.Numeric(precision=24, scale=8), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("changed_by_telegram_id", sa.String(length=20), nullable=True),
        sa.Column("change_source", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("version > 0", name="ck_usdt_rate_override_history_version"),
        sa.CheckConstraint(
            "(is_active AND rate IS NOT NULL AND rate > 0) "
            "OR (NOT is_active AND rate IS NULL)",
            name="ck_usdt_rate_override_history_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version", name="uq_usdt_rate_override_version"),
    )
    op.create_index(
        "ix_usdt_rate_override_history_created",
        "usdt_rate_override_versions",
        ["created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_usdt_rate_override_history_created",
        table_name="usdt_rate_override_versions",
    )
    op.drop_table("usdt_rate_override_versions")
    op.drop_table("usdt_rate_override")
