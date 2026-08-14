"""add Telegram inbox claim fencing

Revision ID: 011
Revises: 010
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "telegram_update_inbox",
        sa.Column("claim_token", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_telegram_update_claim_token_length",
        "telegram_update_inbox",
        "claim_token IS NULL OR char_length(claim_token) BETWEEN 32 AND 64",
    )
    op.execute(
        sa.text(
            "UPDATE telegram_update_inbox "
            "SET payload = '{}'::json, claim_token = NULL, locked_at = NULL "
            "WHERE status IN ('done', 'failed')"
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_telegram_update_claim_token_length",
        "telegram_update_inbox",
        type_="check",
    )
    op.drop_column("telegram_update_inbox", "claim_token")
