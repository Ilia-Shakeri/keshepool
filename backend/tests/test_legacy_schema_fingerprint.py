from copy import deepcopy

from app.services.legacy_schema_fingerprint import (
    BASELINE_COLUMNS,
    BASELINE_CONSTRAINTS,
    BASELINE_ENUMS,
    OPTIONAL_GUARDED_COLUMNS,
    ColumnShape,
    LegacySchemaSnapshot,
    legacy_schema_issues,
)


def complete_snapshot(*, uppercase_enums: bool = False) -> LegacySchemaSnapshot:
    columns = {
        table: {name: sorted(shapes)[0] for name, shapes in definitions.items()}
        for table, definitions in BASELINE_COLUMNS.items()
    }
    enums = {
        name: frozenset(
            label.upper() if uppercase_enums else label for label in labels
        )
        for name, labels in BASELINE_ENUMS.items()
    }
    return LegacySchemaSnapshot(
        columns=columns,
        constraints=deepcopy(BASELINE_CONSTRAINTS),
        enum_labels=enums,
    )


def test_complete_legacy_baseline_is_safe_to_stamp():
    assert legacy_schema_issues(complete_snapshot()) == ()
    assert legacy_schema_issues(complete_snapshot(uppercase_enums=True)) == ()


def test_exact_guarded_columns_are_allowed_before_stamp():
    snapshot = complete_snapshot()
    columns = {table: dict(values) for table, values in snapshot.columns.items()}
    for table, definitions in OPTIONAL_GUARDED_COLUMNS.items():
        for name, shapes in definitions.items():
            columns[table][name] = next(iter(shapes))

    assert legacy_schema_issues(
        LegacySchemaSnapshot(columns, snapshot.constraints, snapshot.enum_labels)
    ) == ()


def test_missing_table_column_and_constraint_stop_stamp():
    snapshot = complete_snapshot()
    columns = {table: dict(values) for table, values in snapshot.columns.items()}
    del columns["notifications"]
    del columns["users"]["telegram_id"]
    constraints = dict(snapshot.constraints)
    constraints["wallets"] = frozenset()

    issues = legacy_schema_issues(
        LegacySchemaSnapshot(columns, constraints, snapshot.enum_labels)
    )

    assert "missing table notifications" in issues
    assert "missing column users.telegram_id" in issues
    assert any(issue.startswith("missing constraint wallets:") for issue in issues)


def test_wrong_or_unknown_shape_stops_stamp():
    snapshot = complete_snapshot()
    columns = {table: dict(values) for table, values in snapshot.columns.items()}
    columns["wallets"]["balance"] = ColumnShape("float8", False)
    columns["users"]["untracked_admin_power"] = ColumnShape("bool", False)
    columns["orders"]["idempotency_key"] = ColumnShape(
        "varchar", True, length=32
    )

    issues = legacy_schema_issues(
        LegacySchemaSnapshot(columns, snapshot.constraints, snapshot.enum_labels)
    )

    assert any(issue.startswith("column wallets.balance is float8") for issue in issues)
    assert "unexpected column users.untracked_admin_power" in issues
    assert any(
        issue.startswith("column orders.idempotency_key is varchar(32)")
        for issue in issues
    )


def test_unknown_enum_label_stops_stamp_without_echoing_rows():
    snapshot = complete_snapshot()
    enums = dict(snapshot.enum_labels)
    enums["transactionstatus"] = frozenset({"pending", "success", "failed", "lost"})

    issues = legacy_schema_issues(
        LegacySchemaSnapshot(snapshot.columns, snapshot.constraints, enums)
    )

    assert issues == ("enum transactionstatus has incompatible labels",)
