import importlib.util
from pathlib import Path

from app.models import InventoryItem, Order, ProductVariant


def _migration_module():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "015_order_commercial_snapshots.py"
    )
    spec = importlib.util.spec_from_file_location("migration_015", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_revision_015_follows_reveal_history_and_never_invents_legacy_labels() -> None:
    migration = _migration_module()
    source = Path(migration.__file__).read_text(encoding="utf-8")

    assert migration.revision == "015"
    assert migration.down_revision == "014"
    assert "SET total_amount_snapshot" not in source
    assert "SET product_title_snapshot" not in source
    assert "SET product_brand_snapshot" not in source
    assert "SET variant_duration_snapshot" not in source
    assert "historical_snapshot_unavailable" in source
    assert "ownership_mismatch" in source


def test_snapshot_schema_has_database_immutability_and_ownership_guards() -> None:
    migration = _migration_module()
    source = Path(migration.__file__).read_text(encoding="utf-8")
    order_constraints = {constraint.name for constraint in Order.__table__.constraints}
    inventory_constraints = {
        constraint.name for constraint in InventoryItem.__table__.constraints
    }
    variant_constraints = {
        constraint.name for constraint in ProductVariant.__table__.constraints
    }
    inventory_indexes = {index.name for index in InventoryItem.__table__.indexes}

    assert "ck_order_commercial_snapshot" in order_constraints
    assert "fk_order_inventory_ownership" in order_constraints
    assert "fk_inventory_product_variant" in inventory_constraints
    assert "uq_inventory_item_ownership" in inventory_constraints
    assert "uq_product_variant_product_id_id" in variant_constraints
    assert "ix_inventory_allocation_fifo" in inventory_indexes
    assert "trg_orders_commercial_snapshot_immutable" in source
    assert "order commercial snapshot is immutable" in source
    assert "order ownership snapshot is immutable" in source
    assert "NOT VALID" in source
    assert "VALIDATE CONSTRAINT" in source


def test_fifo_index_matches_allocation_order() -> None:
    index = next(
        index
        for index in InventoryItem.__table__.indexes
        if index.name == "ix_inventory_allocation_fifo"
    )
    assert [column.name for column in index.columns] == [
        "product_id",
        "variant_id",
        "status",
        "expires_at",
        "created_at",
        "id",
    ]
