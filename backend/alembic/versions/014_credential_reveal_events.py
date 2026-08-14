"""add durable bounded credential reveal history

Revision ID: 014
Revises: 013
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "credential_reveal_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        "ck_orders_credential_reveal_count",
        "orders",
        "credential_reveal_count BETWEEN 0 AND 100",
    )
    op.create_index(
        "ix_orders_user_created_id",
        "orders",
        ["user_id", "created_at", "id"],
    )
    op.create_table(
        "credential_reveal_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_telegram_id", sa.String(length=20), nullable=False),
        sa.Column("order_public_id", sa.String(length=120), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("reveal_count", sa.Integer(), nullable=True),
        sa.Column(
            "request_id",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "outcome IN ('allowed', 'denied_not_found', 'denied_state', "
            "'denied_limit', 'denied_size', 'denied_vault')",
            name="ck_credential_reveal_event_outcome",
        ),
        sa.CheckConstraint(
            "reveal_count IS NULL OR reveal_count BETWEEN 0 AND 100",
            name="ck_credential_reveal_event_count",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_credential_reveal_order_created",
        "credential_reveal_events",
        ["order_id", "created_at", "id"],
    )
    op.create_index(
        "ix_credential_reveal_user_created",
        "credential_reveal_events",
        ["user_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_credential_reveal_user_created",
        table_name="credential_reveal_events",
    )
    op.drop_index(
        "ix_credential_reveal_order_created",
        table_name="credential_reveal_events",
    )
    op.drop_table("credential_reveal_events")
    op.drop_index("ix_orders_user_created_id", table_name="orders")
    op.drop_constraint(
        "ck_orders_credential_reveal_count",
        "orders",
        type_="check",
    )
    op.drop_column("orders", "credential_reveal_count")
