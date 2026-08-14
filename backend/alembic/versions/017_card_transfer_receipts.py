"""add card transfer receipts and durable administrator delivery queue

Revision ID: 017
Revises: 016
Create Date: 2026-08-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_transfer_receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("image_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("receipt_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "receipt_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_card_transfer_receipt_sha256",
        ),
        sa.CheckConstraint(
            "octet_length(image_bytes) BETWEEN 1 AND 5000000",
            name="ck_card_transfer_receipt_size",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_sha256", name="uq_card_transfer_receipts_sha256"),
        sa.UniqueConstraint("transaction_id", name="uq_card_transfer_receipts_transaction_id"),
    )
    op.create_table(
        "card_transfer_admin_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "attempts BETWEEN 0 AND 100",
            name="ck_card_transfer_delivery_attempts",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_card_transfer_delivery_status",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["card_transfer_receipts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "receipt_id",
            "chat_id",
            name="uq_card_transfer_delivery_receipt_chat",
        ),
    )
    op.create_index(
        "ix_card_transfer_delivery_retry",
        "card_transfer_admin_deliveries",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_card_transfer_delivery_retry",
        table_name="card_transfer_admin_deliveries",
    )
    op.drop_table("card_transfer_admin_deliveries")
    op.drop_table("card_transfer_receipts")
