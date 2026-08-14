"""assert exact catalog shape after historical guarded DDL

Revision ID: 016
Revises: 015
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMN_CONTRACTS = {
    ("transactions", "currency"): ("varchar", "NO", 10, None, None),
    ("transactions", "gateway"): ("varchar", "YES", 50, None, None),
    ("transactions", "amount"): ("numeric", "NO", None, 24, 8),
    ("products", "features"): ("text", "YES", None, None, None),
    ("orders", "idempotency_key"): ("varchar", "YES", 64, None, None),
    ("cashout_requests", "id"): ("int4", "NO", None, 32, 0),
    ("cashout_requests", "user_id"): ("int4", "NO", None, 32, 0),
    ("cashout_requests", "source_platform"): ("varchar", "NO", 100, None, None),
    ("cashout_requests", "custom_source"): ("varchar", "YES", 200, None, None),
    ("cashout_requests", "details_text"): ("text", "NO", None, None, None),
    ("cashout_requests", "status"): (
        "cashoutrequeststatus",
        "NO",
        None,
        None,
        None,
    ),
    ("cashout_requests", "created_at"): (
        "timestamptz",
        "NO",
        None,
        None,
        None,
    ),
    ("cashout_requests", "updated_at"): (
        "timestamptz",
        "NO",
        None,
        None,
        None,
    ),
}


INDEX_CONTRACTS = {
    "ix_cashout_requests_id": ("cashout_requests", False, ("id",), None),
    "ix_cashout_requests_user_id": (
        "cashout_requests",
        False,
        ("user_id",),
        None,
    ),
    "ix_cashout_requests_status": (
        "cashout_requests",
        False,
        ("status",),
        None,
    ),
    "ix_cashout_requests_user_created": (
        "cashout_requests",
        False,
        ("user_id", "created_at"),
        None,
    ),
    "uq_orders_user_idempotency_key": (
        "orders",
        True,
        ("user_id", "idempotency_key"),
        "idempotency_key is not null",
    ),
}


def _column_shape(conn, table_name: str, column_name: str):
    row = conn.execute(
        sa.text(
            "SELECT udt_name, is_nullable, character_maximum_length, "
            "numeric_precision, numeric_scale FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table_name "
            "AND column_name = :column_name"
        ),
        {"table_name": table_name, "column_name": column_name},
    ).mappings().one_or_none()
    if row is None:
        return None
    return (
        str(row["udt_name"]),
        str(row["is_nullable"]),
        row["character_maximum_length"],
        row["numeric_precision"],
        row["numeric_scale"],
    )


def _enum_labels(conn, enum_name: str) -> tuple[str, ...]:
    rows = conn.execute(
        sa.text(
            "SELECT enum.enumlabel FROM pg_type typ "
            "JOIN pg_enum enum ON enum.enumtypid = typ.oid "
            "WHERE typ.typname = :enum_name ORDER BY enum.enumsortorder"
        ),
        {"enum_name": enum_name},
    )
    return tuple(str(row[0]) for row in rows)


def _constraint_shape(conn, table_name: str, kind: str):
    rows = conn.execute(
        sa.text(
            "SELECT ARRAY(SELECT att.attname FROM unnest(con.conkey) WITH ORDINALITY "
            "AS key(attnum, ord) JOIN pg_attribute att "
            "ON att.attrelid = con.conrelid AND att.attnum = key.attnum "
            "ORDER BY key.ord) AS columns, ref.relname AS referred_table, "
            "CASE WHEN con.contype = 'f' THEN ARRAY("
            "SELECT att.attname FROM unnest(con.confkey) WITH ORDINALITY "
            "AS key(attnum, ord) JOIN pg_attribute att "
            "ON att.attrelid = con.confrelid AND att.attnum = key.attnum "
            "ORDER BY key.ord) ELSE ARRAY[]::name[] END AS referred_columns "
            "FROM pg_constraint con JOIN pg_class rel ON rel.oid = con.conrelid "
            "JOIN pg_namespace ns ON ns.oid = rel.relnamespace "
            "LEFT JOIN pg_class ref ON ref.oid = con.confrelid "
            "WHERE ns.nspname = 'public' AND rel.relname = :table_name "
            "AND con.contype::text = :kind"
        ),
        {"table_name": table_name, "kind": kind},
    ).mappings()
    return {
        (
            tuple(str(value) for value in row["columns"]),
            str(row["referred_table"]) if row["referred_table"] is not None else None,
            tuple(str(value) for value in row["referred_columns"]),
        )
        for row in rows
    }


def _normalize_predicate(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.replace('"', "").lower().split())
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    return normalized


def _index_shape(conn, index_name: str):
    row = conn.execute(
        sa.text(
            "SELECT rel.relname AS table_name, idx.indisunique, idx.indisvalid, "
            "idx.indisready, ARRAY(SELECT att.attname FROM unnest(idx.indkey) "
            "WITH ORDINALITY AS key(attnum, ord) JOIN pg_attribute att "
            "ON att.attrelid = idx.indrelid AND att.attnum = key.attnum "
            "ORDER BY key.ord) AS columns, "
            "pg_get_expr(idx.indpred, idx.indrelid) AS predicate "
            "FROM pg_index idx JOIN pg_class ind ON ind.oid = idx.indexrelid "
            "JOIN pg_class rel ON rel.oid = idx.indrelid "
            "JOIN pg_namespace ns ON ns.oid = rel.relnamespace "
            "WHERE ns.nspname = 'public' AND ind.relname = :index_name"
        ),
        {"index_name": index_name},
    ).mappings().one_or_none()
    if row is None:
        return None
    return (
        str(row["table_name"]),
        bool(row["indisunique"]),
        bool(row["indisvalid"]),
        bool(row["indisready"]),
        tuple(str(value) for value in row["columns"]),
        _normalize_predicate(row["predicate"]),
    )


def guarded_schema_issues(conn) -> tuple[str, ...]:
    issues: list[str] = []
    for (table_name, column_name), expected in COLUMN_CONTRACTS.items():
        actual = _column_shape(conn, table_name, column_name)
        if actual != expected:
            issues.append(
                f"column {table_name}.{column_name} is {actual!r}; expected {expected!r}"
            )

    labels = _enum_labels(conn, "cashoutrequeststatus")
    expected_labels = ("pending", "reviewed", "completed")
    if labels != expected_labels:
        issues.append(
            f"enum cashoutrequeststatus is {labels!r}; expected {expected_labels!r}"
        )

    primary_keys = _constraint_shape(conn, "cashout_requests", "p")
    if primary_keys != {(('id',), None, ())}:
        issues.append("cashout_requests primary key does not match (id)")
    foreign_keys = _constraint_shape(conn, "cashout_requests", "f")
    if foreign_keys != {(('user_id',), 'users', ('id',))}:
        issues.append("cashout_requests foreign key does not match users(id)")

    for index_name, expected in INDEX_CONTRACTS.items():
        actual = _index_shape(conn, index_name)
        if actual is None:
            issues.append(f"missing index {index_name}")
            continue
        table_name, unique, valid, ready, columns, predicate = actual
        expected_table, expected_unique, expected_columns, expected_predicate = expected
        if (
            table_name != expected_table
            or unique != expected_unique
            or not valid
            or not ready
            or columns != expected_columns
            or predicate != expected_predicate
        ):
            issues.append(f"index {index_name} does not match its release contract")
    return tuple(issues)


def upgrade() -> None:
    issues = guarded_schema_issues(op.get_bind())
    if issues:
        details = "\n".join(f"- {issue}" for issue in issues)
        raise RuntimeError(
            "Guarded schema catalog mismatch; add an operator-reviewed corrective "
            f"migration before retrying:\n{details}"
        )


def downgrade() -> None:
    pass
