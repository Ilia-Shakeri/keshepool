from dataclasses import dataclass
from typing import Iterable, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


BASELINE_TABLES = (
    "users",
    "wallets",
    "transactions",
    "products",
    "product_variants",
    "inventory_items",
    "orders",
    "notifications",
)


@dataclass(frozen=True, order=True)
class ColumnShape:
    type_name: str
    nullable: bool
    length: int | None = None
    precision: int | None = None
    scale: int | None = None


@dataclass(frozen=True, order=True)
class ConstraintShape:
    kind: str
    columns: tuple[str, ...]
    referred_table: str | None = None
    referred_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class LegacySchemaSnapshot:
    columns: Mapping[str, Mapping[str, ColumnShape]]
    constraints: Mapping[str, frozenset[ConstraintShape]]
    enum_labels: Mapping[str, frozenset[str]]


def _varchar(nullable: bool, length: int | None = None) -> ColumnShape:
    return ColumnShape("varchar", nullable, length=length)


def _numeric(nullable: bool, precision: int, scale: int) -> ColumnShape:
    return ColumnShape("numeric", nullable, precision=precision, scale=scale)


BASELINE_COLUMNS: dict[str, dict[str, frozenset[ColumnShape]]] = {
    "users": {
        "id": frozenset({ColumnShape("int4", False)}),
        "telegram_id": frozenset({_varchar(False)}),
        "username": frozenset({_varchar(True)}),
        "first_name": frozenset({_varchar(True)}),
        "last_name": frozenset({_varchar(True)}),
        "language_code": frozenset({_varchar(True)}),
        "photo_url": frozenset({_varchar(True)}),
        "is_premium": frozenset({ColumnShape("bool", False)}),
        "role": frozenset({_varchar(False)}),
        "referrer_id": frozenset({ColumnShape("int4", True)}),
        "last_seen_at": frozenset({ColumnShape("timestamptz", False)}),
        "created_at": frozenset({ColumnShape("timestamptz", False)}),
        "updated_at": frozenset({ColumnShape("timestamptz", False)}),
    },
    "wallets": {
        "id": frozenset({ColumnShape("int4", False)}),
        "user_id": frozenset({ColumnShape("int4", False)}),
        "balance": frozenset({_numeric(False, 18, 2)}),
    },
    "transactions": {
        "id": frozenset({ColumnShape("int4", False)}),
        "wallet_id": frozenset({ColumnShape("int4", False)}),
        "amount": frozenset({_numeric(False, 18, 2), _numeric(False, 24, 8)}),
        "type": frozenset({ColumnShape("transactiontype", False)}),
        "status": frozenset({ColumnShape("transactionstatus", False)}),
        "reference_id": frozenset({_varchar(True)}),
        "description": frozenset({_varchar(True)}),
        "created_at": frozenset({ColumnShape("timestamptz", False)}),
    },
    "products": {
        "id": frozenset({_varchar(False)}),
        "title": frozenset({_varchar(False)}),
        "brand": frozenset({_varchar(False)}),
        "subtitle": frozenset({_varchar(True)}),
        "icon": frozenset({_varchar(False)}),
        "asset_url": frozenset({_varchar(True)}),
        "gradient": frozenset({_varchar(False)}),
        "category": frozenset({_varchar(False)}),
        "is_active": frozenset({ColumnShape("bool", False)}),
        "created_at": frozenset({ColumnShape("timestamptz", False)}),
        "updated_at": frozenset({ColumnShape("timestamptz", False)}),
    },
    "product_variants": {
        "id": frozenset({_varchar(False)}),
        "product_id": frozenset({_varchar(False)}),
        "duration": frozenset({_varchar(False)}),
        "price_label": frozenset({_varchar(False)}),
        "raw_price": frozenset({_numeric(False, 18, 2)}),
        "is_active": frozenset({ColumnShape("bool", False)}),
    },
    "inventory_items": {
        "id": frozenset({ColumnShape("int4", False)}),
        "product_id": frozenset({_varchar(False)}),
        "variant_id": frozenset({_varchar(False)}),
        "credentials": frozenset({ColumnShape("text", False)}),
        "status": frozenset({ColumnShape("itemstatus", False)}),
        "assigned_to_user_id": frozenset({ColumnShape("int4", True)}),
        "expires_at": frozenset({ColumnShape("timestamptz", True)}),
        "assigned_at": frozenset({ColumnShape("timestamptz", True)}),
        "created_at": frozenset({ColumnShape("timestamptz", False)}),
    },
    "orders": {
        "id": frozenset({ColumnShape("int4", False)}),
        "public_id": frozenset({_varchar(False)}),
        "user_id": frozenset({ColumnShape("int4", False)}),
        "product_id": frozenset({_varchar(False)}),
        "variant_id": frozenset({_varchar(False)}),
        "inventory_item_id": frozenset({ColumnShape("int4", False)}),
        "total_amount": frozenset({_numeric(False, 18, 2)}),
        "status": frozenset({ColumnShape("orderstatus", False)}),
        "created_at": frozenset({ColumnShape("timestamptz", False)}),
        "expires_at": frozenset({ColumnShape("timestamptz", True)}),
    },
    "notifications": {
        "id": frozenset({ColumnShape("int4", False)}),
        "user_id": frozenset({ColumnShape("int4", False)}),
        "title": frozenset({_varchar(False)}),
        "description": frozenset({ColumnShape("text", False)}),
        "is_read": frozenset({ColumnShape("bool", False)}),
        "created_at": frozenset({ColumnShape("timestamptz", False)}),
    },
}


OPTIONAL_GUARDED_COLUMNS: dict[str, dict[str, frozenset[ColumnShape]]] = {
    "transactions": {
        "currency": frozenset({_varchar(False, 10)}),
        "gateway": frozenset({_varchar(True, 50)}),
    },
    "products": {"features": frozenset({ColumnShape("text", True)})},
    "orders": {"idempotency_key": frozenset({_varchar(True, 64)})},
}


def _pk(*columns: str) -> ConstraintShape:
    return ConstraintShape("p", columns)


def _uq(*columns: str) -> ConstraintShape:
    return ConstraintShape("u", columns)


def _fk(
    columns: tuple[str, ...],
    referred_table: str,
    referred_columns: tuple[str, ...],
) -> ConstraintShape:
    return ConstraintShape("f", columns, referred_table, referred_columns)


BASELINE_CONSTRAINTS: dict[str, frozenset[ConstraintShape]] = {
    "users": frozenset({_pk("id"), _fk(("referrer_id",), "users", ("id",))}),
    "wallets": frozenset(
        {_pk("id"), _uq("user_id"), _fk(("user_id",), "users", ("id",))}
    ),
    "transactions": frozenset(
        {_pk("id"), _fk(("wallet_id",), "wallets", ("id",))}
    ),
    "products": frozenset({_pk("id")}),
    "product_variants": frozenset(
        {_pk("id"), _fk(("product_id",), "products", ("id",))}
    ),
    "inventory_items": frozenset(
        {
            _pk("id"),
            _uq("product_id", "variant_id", "credentials"),
            _fk(("assigned_to_user_id",), "users", ("id",)),
            _fk(("product_id",), "products", ("id",)),
            _fk(("variant_id",), "product_variants", ("id",)),
        }
    ),
    "orders": frozenset(
        {
            _pk("id"),
            _uq("inventory_item_id"),
            _fk(("inventory_item_id",), "inventory_items", ("id",)),
            _fk(("product_id",), "products", ("id",)),
            _fk(("user_id",), "users", ("id",)),
            _fk(("variant_id",), "product_variants", ("id",)),
        }
    ),
    "notifications": frozenset(
        {_pk("id"), _fk(("user_id",), "users", ("id",))}
    ),
}


BASELINE_ENUMS: dict[str, tuple[str, ...]] = {
    "itemstatus": ("available", "reserved", "assigned", "expired", "disabled"),
    "transactiontype": (
        "deposit_irr",
        "deposit_crypto",
        "purchase",
        "cashout",
        "refund",
        "referral_bonus",
    ),
    "transactionstatus": ("pending", "success", "failed"),
    "orderstatus": ("active", "expired", "cancelled", "refunded"),
}


def _format_column(shape: ColumnShape) -> str:
    suffix = "?" if shape.nullable else "!"
    if shape.length is not None:
        return f"{shape.type_name}({shape.length}){suffix}"
    if shape.precision is not None:
        return f"{shape.type_name}({shape.precision},{shape.scale}){suffix}"
    return f"{shape.type_name}{suffix}"


def _enum_shape_is_compatible(actual: frozenset[str], expected: Iterable[str]) -> bool:
    expected_values = tuple(expected)
    allowed = {value for label in expected_values for value in (label, label.upper())}
    return actual <= allowed and all(
        label in actual or label.upper() in actual for label in expected_values
    )


def legacy_schema_issues(snapshot: LegacySchemaSnapshot) -> tuple[str, ...]:
    issues: list[str] = []
    for table in BASELINE_TABLES:
        actual_columns = snapshot.columns.get(table)
        if actual_columns is None:
            issues.append(f"missing table {table}")
            continue

        expected_columns = BASELINE_COLUMNS[table]
        optional_columns = OPTIONAL_GUARDED_COLUMNS.get(table, {})
        allowed_names = set(expected_columns) | set(optional_columns)
        for name in sorted(set(actual_columns) - allowed_names):
            issues.append(f"unexpected column {table}.{name}")
        for name, allowed_shapes in expected_columns.items():
            actual = actual_columns.get(name)
            if actual is None:
                issues.append(f"missing column {table}.{name}")
            elif actual not in allowed_shapes:
                allowed = "/".join(sorted(_format_column(shape) for shape in allowed_shapes))
                issues.append(
                    f"column {table}.{name} is {_format_column(actual)}; expected {allowed}"
                )
        for name, allowed_shapes in optional_columns.items():
            actual = actual_columns.get(name)
            if actual is not None and actual not in allowed_shapes:
                allowed = "/".join(sorted(_format_column(shape) for shape in allowed_shapes))
                issues.append(
                    f"column {table}.{name} is {_format_column(actual)}; expected {allowed}"
                )

        actual_constraints = snapshot.constraints.get(table, frozenset())
        expected_constraints = BASELINE_CONSTRAINTS[table]
        for missing in sorted(expected_constraints - actual_constraints):
            issues.append(f"missing constraint {table}:{missing}")
        for extra in sorted(actual_constraints - expected_constraints):
            issues.append(f"unexpected constraint {table}:{extra}")

    for enum_name, expected_labels in BASELINE_ENUMS.items():
        actual_labels = snapshot.enum_labels.get(enum_name)
        if actual_labels is None:
            issues.append(f"missing enum {enum_name}")
        elif not _enum_shape_is_compatible(actual_labels, expected_labels):
            issues.append(f"enum {enum_name} has incompatible labels")
    return tuple(issues)


async def load_legacy_schema_snapshot(conn: AsyncConnection) -> LegacySchemaSnapshot:
    table_sql = ", ".join(f"'{table}'" for table in BASELINE_TABLES)
    column_rows = (
        await conn.execute(
            text(
                "SELECT table_name, column_name, udt_name, is_nullable, "
                "character_maximum_length, numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                f"WHERE table_schema = 'public' AND table_name IN ({table_sql})"
            )
        )
    ).mappings()
    columns: dict[str, dict[str, ColumnShape]] = {}
    for row in column_rows:
        columns.setdefault(str(row["table_name"]), {})[str(row["column_name"])] = (
            ColumnShape(
                type_name=str(row["udt_name"]),
                nullable=str(row["is_nullable"]) == "YES",
                length=row["character_maximum_length"],
                precision=row["numeric_precision"],
                scale=row["numeric_scale"],
            )
        )

    constraint_rows = (
        await conn.execute(
            text(
                "SELECT rel.relname AS table_name, con.contype AS kind, "
                "ARRAY(SELECT att.attname FROM unnest(con.conkey) WITH ORDINALITY "
                "AS key(attnum, ord) JOIN pg_attribute att "
                "ON att.attrelid = con.conrelid AND att.attnum = key.attnum "
                "ORDER BY key.ord) AS columns, "
                "ref.relname AS referred_table, "
                "CASE WHEN con.contype = 'f' THEN ARRAY("
                "SELECT att.attname FROM unnest(con.confkey) WITH ORDINALITY "
                "AS key(attnum, ord) JOIN pg_attribute att "
                "ON att.attrelid = con.confrelid AND att.attnum = key.attnum "
                "ORDER BY key.ord) ELSE ARRAY[]::name[] END AS referred_columns "
                "FROM pg_constraint con "
                "JOIN pg_class rel ON rel.oid = con.conrelid "
                "JOIN pg_namespace ns ON ns.oid = rel.relnamespace "
                "LEFT JOIN pg_class ref ON ref.oid = con.confrelid "
                f"WHERE ns.nspname = 'public' AND rel.relname IN ({table_sql}) "
                "AND con.contype IN ('p', 'u', 'f')"
            )
        )
    ).mappings()
    constraints: dict[str, set[ConstraintShape]] = {}
    for row in constraint_rows:
        constraints.setdefault(str(row["table_name"]), set()).add(
            ConstraintShape(
                kind=str(row["kind"]),
                columns=tuple(str(value) for value in row["columns"]),
                referred_table=(
                    str(row["referred_table"])
                    if row["referred_table"] is not None
                    else None
                ),
                referred_columns=tuple(
                    str(value) for value in row["referred_columns"]
                ),
            )
        )

    enum_names = ", ".join(f"'{name}'" for name in BASELINE_ENUMS)
    enum_rows = (
        await conn.execute(
            text(
                "SELECT typ.typname AS enum_name, enum.enumlabel "
                "FROM pg_type typ JOIN pg_enum enum ON enum.enumtypid = typ.oid "
                f"WHERE typ.typname IN ({enum_names})"
            )
        )
    ).mappings()
    enums: dict[str, set[str]] = {}
    for row in enum_rows:
        enums.setdefault(str(row["enum_name"]), set()).add(str(row["enumlabel"]))

    return LegacySchemaSnapshot(
        columns=columns,
        constraints={name: frozenset(values) for name, values in constraints.items()},
        enum_labels={name: frozenset(values) for name, values in enums.items()},
    )
