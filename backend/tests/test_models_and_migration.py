import importlib.util
from pathlib import Path

from sqlalchemy.dialects import postgresql

from app.models import (
    AdminAuditLog,
    CashoutRequest,
    CashoutRequestStatus,
    InventoryItem,
    ItemStatus,
    Order,
    OrderStatus,
    Transaction,
    TransactionStatus,
    TransactionType,
)


def _migration_module():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "004_enum_values_transaction_precision_checkout_idempotency.py"
    )
    spec = importlib.util.spec_from_file_location("migration_004", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_all_model_enums_bind_lowercase_values_and_read_enum_members():
    dialect = postgresql.dialect()
    cases = (
        (InventoryItem.__table__.c.status.type, ItemStatus.AVAILABLE, "available", "itemstatus"),
        (
            Transaction.__table__.c.type.type,
            TransactionType.DEPOSIT_CRYPTO,
            "deposit_crypto",
            "transactiontype",
        ),
        (
            Transaction.__table__.c.status.type,
            TransactionStatus.SUCCESS,
            "success",
            "transactionstatus",
        ),
        (Order.__table__.c.status.type, OrderStatus.ACTIVE, "active", "orderstatus"),
        (
            CashoutRequest.__table__.c.status.type,
            CashoutRequestStatus.REVIEWED,
            "reviewed",
            "cashoutrequeststatus",
        ),
    )

    for enum_type, member, stored_value, type_name in cases:
        bind = enum_type.bind_processor(dialect)
        result = enum_type.result_processor(dialect, None)
        assert bind is not None
        assert result is not None
        assert enum_type.name == type_name
        assert bind(member) == stored_value
        assert result(stored_value) is member


def test_order_idempotency_index_matches_migration_shape():
    index = next(
        item for item in Order.__table__.indexes if item.name == "uq_orders_user_idempotency_key"
    )
    assert index.unique is True
    assert [column.name for column in index.columns] == ["user_id", "idempotency_key"]
    assert "idempotency_key IS NOT NULL" in str(index.dialect_options["postgresql"]["where"])


def test_admin_audit_json_default_matches_migration():
    server_default = AdminAuditLog.__table__.c.details.server_default
    assert server_default is not None
    assert str(server_default.arg) == "'{}'::json"


def test_migration_uses_literal_enum_ddl_and_never_rebuilds_types():
    migration = _migration_module()

    class FakeConnection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, parameters=None):
            self.calls.append((str(statement), parameters))

    connection = FakeConnection()
    migration._rename_enum_label(
        connection,
        "itemstatus",
        "AVAILABLE",
        "available",
    )
    ddl, parameters = connection.calls[0]
    assert parameters is None
    assert "RENAME VALUE 'AVAILABLE' TO 'available'" in ddl
    source = Path(migration.__file__).read_text(encoding="utf-8")
    assert "DROP TYPE" not in source.upper()
    assert "ENUM_DEFINITIONS" in source


def test_migration_moves_rows_when_both_enum_labels_already_exist():
    migration = _migration_module()

    class FakeConnection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, parameters=None):
            self.calls.append((str(statement), parameters))

    connection = FakeConnection()
    migration._move_rows_to_existing_label(
        connection,
        "itemstatus",
        (("inventory_items", "status"),),
        "AVAILABLE",
        "available",
    )
    sql, parameters = connection.calls[0]
    assert 'CAST(:new AS "itemstatus")' in sql
    assert parameters == {"new": "available", "old": "AVAILABLE"}
