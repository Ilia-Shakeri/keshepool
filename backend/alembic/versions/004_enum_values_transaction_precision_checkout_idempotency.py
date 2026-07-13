"""normalize enum labels, transaction precision, and checkout idempotency

Revision ID: 004
Revises: 003
Create Date: 2026-07-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENUM_DEFINITIONS = {
    "itemstatus": {
        "labels": ("available", "reserved", "assigned", "expired", "disabled"),
        "columns": (("inventory_items", "status"),),
    },
    "transactiontype": {
        "labels": (
            "deposit_irr",
            "deposit_crypto",
            "purchase",
            "cashout",
            "refund",
            "referral_bonus",
        ),
        "columns": (("transactions", "type"),),
    },
    "transactionstatus": {
        "labels": ("pending", "success", "failed"),
        "columns": (("transactions", "status"),),
    },
    "orderstatus": {
        "labels": ("active", "expired", "cancelled", "refunded"),
        "columns": (("orders", "status"),),
    },
    "cashoutrequeststatus": {
        "labels": ("pending", "reviewed", "completed"),
        "columns": (("cashout_requests", "status"),),
    },
}


def _labels(conn, type_name: str) -> set[str]:
    rows = conn.execute(
        sa.text(
            "SELECT e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid WHERE t.typname = :type_name"
        ),
        {"type_name": type_name},
    )
    return {row[0] for row in rows}


def _sql_literal(value: str) -> str:
    """Quote a fixed enum label for PostgreSQL DDL, which cannot use bind values."""
    return "'" + value.replace("'", "''") + "'"


def _rename_enum_label(conn, type_name: str, old: str, new: str) -> None:
    conn.execute(
        sa.text(
            f'ALTER TYPE "{type_name}" RENAME VALUE '
            f"{_sql_literal(old)} TO {_sql_literal(new)}"
        )
    )


def _move_rows_to_existing_label(
    conn,
    type_name: str,
    columns: tuple[tuple[str, str], ...],
    old: str,
    new: str,
) -> None:
    # PostgreSQL cannot remove an enum label without rebuilding the type. When both
    # labels exist, move live rows to the canonical value and leave the unused legacy
    # label in place so populated databases are never rebuilt.
    for table_name, column_name in columns:
        conn.execute(
            sa.text(
                f'UPDATE "{table_name}" SET "{column_name}" = '
                f'CAST(:new AS "{type_name}") '
                f'WHERE "{column_name}" = CAST(:old AS "{type_name}")'
            ),
            {"new": new, "old": old},
        )


def upgrade() -> None:
    conn = op.get_bind()

    for type_name, definition in ENUM_DEFINITIONS.items():
        labels = _labels(conn, type_name)
        columns = definition["columns"]
        for lower in definition["labels"]:
            upper = lower.upper()
            if upper not in labels:
                continue
            if lower in labels:
                _move_rows_to_existing_label(conn, type_name, columns, upper, lower)
            else:
                _rename_enum_label(conn, type_name, upper, lower)
                labels.remove(upper)
                labels.add(lower)

    conn.execute(sa.text("ALTER TABLE transactions ALTER COLUMN amount TYPE NUMERIC(24, 8)"))
    conn.execute(sa.text("ALTER TABLE orders ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(64)"))
    conn.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_user_idempotency_key "
            "ON orders (user_id, idempotency_key) WHERE idempotency_key IS NOT NULL"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP INDEX IF EXISTS uq_orders_user_idempotency_key"))
    conn.execute(sa.text("ALTER TABLE orders DROP COLUMN IF EXISTS idempotency_key"))
    conn.execute(sa.text("ALTER TABLE transactions ALTER COLUMN amount TYPE NUMERIC(18, 2)"))
