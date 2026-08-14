import importlib.util
from pathlib import Path


def load_migration():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "016_guarded_schema_assertions.py"
    )
    spec = importlib.util.spec_from_file_location("migration_016", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def install_matching_catalog(monkeypatch, migration):
    monkeypatch.setattr(
        migration,
        "_column_shape",
        lambda _conn, table, column: migration.COLUMN_CONTRACTS[(table, column)],
    )
    monkeypatch.setattr(
        migration,
        "_enum_labels",
        lambda _conn, _name: ("pending", "reviewed", "completed"),
    )
    monkeypatch.setattr(
        migration,
        "_constraint_shape",
        lambda _conn, _table, kind: (
            {(('id',), None, ())}
            if kind == "p"
            else {(('user_id',), 'users', ('id',))}
        ),
    )

    def index_shape(_conn, index_name):
        table, unique, columns, predicate = migration.INDEX_CONTRACTS[index_name]
        return table, unique, True, True, columns, predicate

    monkeypatch.setattr(migration, "_index_shape", index_shape)


def test_revision_016_follows_snapshot_revision_and_is_assertion_only():
    migration = load_migration()

    assert migration.revision == "016"
    assert migration.down_revision == "015"
    assert callable(migration.guarded_schema_issues)
    assert migration.downgrade() is None


def test_matching_guarded_catalog_has_no_issues(monkeypatch):
    migration = load_migration()
    install_matching_catalog(monkeypatch, migration)

    assert migration.guarded_schema_issues(object()) == ()


def test_column_enum_constraint_and_index_drift_are_all_reported(monkeypatch):
    migration = load_migration()
    install_matching_catalog(monkeypatch, migration)
    monkeypatch.setattr(migration, "_column_shape", lambda *_args: None)
    monkeypatch.setattr(migration, "_enum_labels", lambda *_args: ("PENDING",))
    monkeypatch.setattr(migration, "_constraint_shape", lambda *_args: set())
    monkeypatch.setattr(migration, "_index_shape", lambda *_args: None)

    issues = migration.guarded_schema_issues(object())

    assert any(issue.startswith("column transactions.currency") for issue in issues)
    assert any(issue.startswith("enum cashoutrequeststatus") for issue in issues)
    assert "cashout_requests primary key does not match (id)" in issues
    assert "cashout_requests foreign key does not match users(id)" in issues
    assert "missing index uq_orders_user_idempotency_key" in issues


def test_predicate_normalization_is_stable():
    migration = load_migration()

    assert migration._normalize_predicate('(("idempotency_key" IS NOT NULL))') == (
        "idempotency_key is not null"
    )


def test_constraint_kind_is_compared_as_text_for_asyncpg():
    migration = load_migration()
    captured = {}

    class Result:
        def mappings(self):
            return ()

    class Connection:
        def execute(self, statement, parameters):
            captured["sql"] = str(statement)
            captured["parameters"] = parameters
            return Result()

    assert migration._constraint_shape(Connection(), "cashout_requests", "p") == set()
    assert "con.contype::text = :kind" in captured["sql"]
    assert captured["parameters"] == {
        "table_name": "cashout_requests",
        "kind": "p",
    }
