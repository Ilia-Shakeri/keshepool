"""add currency and gateway to transactions; add cashout_requests table

Revision ID: 002
Revises: 001
Create Date: 2026-06-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── transactions: add currency column ──────────────────────────────────────
    # Nullable first so existing rows don't violate NOT NULL, then backfill,
    # then tighten to NOT NULL.
    op.add_column(
        "transactions",
        sa.Column("currency", sa.String(10), nullable=True),
    )
    op.execute("UPDATE transactions SET currency = 'IRR' WHERE currency IS NULL")
    op.alter_column("transactions", "currency", nullable=False)

    # ── transactions: add gateway column ─────────────────────────────────────
    op.add_column(
        "transactions",
        sa.Column("gateway", sa.String(50), nullable=True),
    )

    # ── cashout_requests ──────────────────────────────────────────────────────
    cashoutrequeststatus = sa.Enum(
        "pending", "reviewed", "completed",
        name="cashoutrequeststatus",
    )
    cashoutrequeststatus.create(op.get_bind())

    op.create_table(
        "cashout_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_platform", sa.String(100), nullable=False),
        sa.Column("custom_source", sa.String(200), nullable=True),
        sa.Column("details_text", sa.Text(), nullable=False),
        sa.Column("status", cashoutrequeststatus, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cashout_requests_id", "cashout_requests", ["id"])
    op.create_index("ix_cashout_requests_user_id", "cashout_requests", ["user_id"])
    op.create_index("ix_cashout_requests_status", "cashout_requests", ["status"])
    op.create_index(
        "ix_cashout_requests_user_created",
        "cashout_requests",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cashout_requests_user_created", "cashout_requests")
    op.drop_index("ix_cashout_requests_status", "cashout_requests")
    op.drop_index("ix_cashout_requests_user_id", "cashout_requests")
    op.drop_index("ix_cashout_requests_id", "cashout_requests")
    op.drop_table("cashout_requests")

    sa.Enum(name="cashoutrequeststatus").drop(op.get_bind())

    op.drop_column("transactions", "gateway")
    op.drop_column("transactions", "currency")
