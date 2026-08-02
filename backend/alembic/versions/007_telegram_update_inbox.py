"""add durable Telegram update inbox

Revision ID: 007
Revises: 006
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_update_inbox",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_type", sa.String(length=10), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("attempts >= 0", name="ck_telegram_update_attempts"),
        sa.CheckConstraint("bot_type IN ('main', 'admin')", name="ck_telegram_update_bot_type"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'retry', 'done', 'failed')",
            name="ck_telegram_update_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bot_type", "update_id", name="uq_telegram_update_bot_id"),
    )
    op.create_index(
        "ix_telegram_update_claim",
        "telegram_update_inbox",
        ["status", "next_attempt_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_update_claim", table_name="telegram_update_inbox")
    op.drop_table("telegram_update_inbox")
