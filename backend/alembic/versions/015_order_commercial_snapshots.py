"""add immutable order snapshots and relational ownership guards

Revision ID: 015
Revises: 014
Create Date: 2026-08-02
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_foreign_key(
    table_name: str,
    constrained_columns: tuple[str, ...],
    referred_table: str,
) -> None:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(table_name):
        if (
            tuple(foreign_key.get("constrained_columns") or ()) == constrained_columns
            and foreign_key.get("referred_table") == referred_table
        ):
            constraint_name = foreign_key.get("name")
            if not constraint_name:
                raise RuntimeError(f"Unnamed foreign key on {table_name} cannot be replaced.")
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")
            return
    raise RuntimeError(f"Expected foreign key on {table_name} was not found.")


def _has_inventory_ownership_mismatch() -> bool:
    return bool(
        op.get_bind().scalar(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM inventory_items i "
                "LEFT JOIN product_variants v ON v.id = i.variant_id "
                "AND v.product_id = i.product_id "
                "WHERE v.id IS NULL)"
            )
        )
    )


def _has_order_ownership_mismatch() -> bool:
    return bool(
        op.get_bind().scalar(
            sa.text(
                "SELECT EXISTS ("
                "SELECT 1 FROM orders o "
                "LEFT JOIN inventory_items i ON i.id = o.inventory_item_id "
                "AND i.product_id = o.product_id "
                "AND i.variant_id = o.variant_id "
                "WHERE i.id IS NULL)"
            )
        )
    )


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("product_title_snapshot", sa.String(length=180), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("product_brand_snapshot", sa.String(length=180), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("variant_duration_snapshot", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("variant_price_label_snapshot", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("currency_snapshot", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("unit_price_amount", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("fee_amount", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("total_amount_snapshot", sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "snapshot_state",
            sa.String(length=24),
            nullable=False,
            server_default="legacy_quarantined",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "snapshot_quarantine_reason",
            sa.String(length=64),
            nullable=True,
            server_default="historical_snapshot_unavailable",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE orders o SET snapshot_quarantine_reason = 'ownership_mismatch' "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM inventory_items i "
            "JOIN product_variants v ON v.id = i.variant_id "
            "AND v.product_id = i.product_id "
            "WHERE i.id = o.inventory_item_id "
            "AND i.product_id = o.product_id "
            "AND i.variant_id = o.variant_id)"
        )
    )
    op.create_check_constraint(
        "ck_order_commercial_snapshot",
        "orders",
        "(snapshot_state = 'complete' "
        "AND snapshot_quarantine_reason IS NULL "
        "AND product_title_snapshot IS NOT NULL "
        "AND char_length(product_title_snapshot) > 0 "
        "AND product_brand_snapshot IS NOT NULL "
        "AND char_length(product_brand_snapshot) > 0 "
        "AND variant_duration_snapshot IS NOT NULL "
        "AND char_length(variant_duration_snapshot) > 0 "
        "AND variant_price_label_snapshot IS NOT NULL "
        "AND char_length(variant_price_label_snapshot) > 0 "
        "AND currency_snapshot IS NOT NULL "
        "AND char_length(currency_snapshot) BETWEEN 3 AND 10 "
        "AND unit_price_amount IS NOT NULL AND unit_price_amount >= 0 "
        "AND tax_amount IS NOT NULL AND tax_amount >= 0 "
        "AND fee_amount IS NOT NULL AND fee_amount >= 0 "
        "AND total_amount_snapshot IS NOT NULL AND total_amount_snapshot >= 0 "
        "AND total_amount_snapshot = unit_price_amount + tax_amount + fee_amount "
        "AND total_amount = total_amount_snapshot) OR "
        "(snapshot_state = 'legacy_quarantined' "
        "AND snapshot_quarantine_reason IN ("
        "'historical_snapshot_unavailable', 'ownership_mismatch') "
        "AND (total_amount_snapshot IS NULL "
        "OR total_amount_snapshot = total_amount))",
    )
    op.create_index(
        "ix_orders_snapshot_state_created",
        "orders",
        ["snapshot_state", "created_at", "id"],
    )

    op.create_unique_constraint(
        "uq_product_variant_product_id_id",
        "product_variants",
        ["product_id", "id"],
    )
    op.create_unique_constraint(
        "uq_inventory_item_ownership",
        "inventory_items",
        ["id", "product_id", "variant_id"],
    )
    _drop_foreign_key("inventory_items", ("variant_id",), "product_variants")
    _drop_foreign_key("orders", ("inventory_item_id",), "inventory_items")

    op.execute(
        sa.text(
            "UPDATE inventory_items i SET status = 'disabled'::itemstatus "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM product_variants v "
            "WHERE v.id = i.variant_id AND v.product_id = i.product_id)"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE inventory_items ADD CONSTRAINT "
            "fk_inventory_product_variant FOREIGN KEY (product_id, variant_id) "
            "REFERENCES product_variants (product_id, id) NOT VALID"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE orders ADD CONSTRAINT fk_order_inventory_ownership "
            "FOREIGN KEY (inventory_item_id, product_id, variant_id) "
            "REFERENCES inventory_items (id, product_id, variant_id) NOT VALID"
        )
    )
    if not _has_inventory_ownership_mismatch():
        op.execute(
            "ALTER TABLE inventory_items VALIDATE CONSTRAINT "
            "fk_inventory_product_variant"
        )
    if not _has_order_ownership_mismatch():
        op.execute(
            "ALTER TABLE orders VALIDATE CONSTRAINT fk_order_inventory_ownership"
        )

    op.create_index(
        "ix_inventory_allocation_fifo",
        "inventory_items",
        ["product_id", "variant_id", "status", "expires_at", "created_at", "id"],
    )
    op.execute(
        sa.text(
            "CREATE FUNCTION keshepool_protect_order_commercial_snapshot() "
            "RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN "
            "IF ROW(OLD.product_title_snapshot, OLD.product_brand_snapshot, "
            "OLD.variant_duration_snapshot, OLD.variant_price_label_snapshot, "
            "OLD.currency_snapshot, OLD.unit_price_amount, OLD.tax_amount, "
            "OLD.fee_amount, OLD.total_amount_snapshot, OLD.total_amount, "
            "OLD.snapshot_state, OLD.snapshot_quarantine_reason) "
            "IS DISTINCT FROM "
            "ROW(NEW.product_title_snapshot, NEW.product_brand_snapshot, "
            "NEW.variant_duration_snapshot, NEW.variant_price_label_snapshot, "
            "NEW.currency_snapshot, NEW.unit_price_amount, NEW.tax_amount, "
            "NEW.fee_amount, NEW.total_amount_snapshot, NEW.total_amount, "
            "NEW.snapshot_state, NEW.snapshot_quarantine_reason) THEN "
            "RAISE EXCEPTION 'order commercial snapshot is immutable'; "
            "END IF; "
            "IF OLD.snapshot_state = 'complete' AND "
            "ROW(OLD.product_id, OLD.variant_id, OLD.inventory_item_id) "
            "IS DISTINCT FROM "
            "ROW(NEW.product_id, NEW.variant_id, NEW.inventory_item_id) THEN "
            "RAISE EXCEPTION 'order ownership snapshot is immutable'; "
            "END IF; RETURN NEW; END; $$"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_orders_commercial_snapshot_immutable "
            "BEFORE UPDATE ON orders FOR EACH ROW "
            "EXECUTE FUNCTION keshepool_protect_order_commercial_snapshot()"
        )
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_orders_commercial_snapshot_immutable ON orders")
    op.execute("DROP FUNCTION IF EXISTS keshepool_protect_order_commercial_snapshot()")
    op.drop_index("ix_inventory_allocation_fifo", table_name="inventory_items")
    op.drop_constraint("fk_order_inventory_ownership", "orders", type_="foreignkey")
    op.drop_constraint(
        "fk_inventory_product_variant",
        "inventory_items",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "inventory_items_variant_id_fkey",
        "inventory_items",
        "product_variants",
        ["variant_id"],
        ["id"],
    )
    op.create_foreign_key(
        "orders_inventory_item_id_fkey",
        "orders",
        "inventory_items",
        ["inventory_item_id"],
        ["id"],
    )
    op.drop_constraint(
        "uq_inventory_item_ownership",
        "inventory_items",
        type_="unique",
    )
    op.drop_constraint(
        "uq_product_variant_product_id_id",
        "product_variants",
        type_="unique",
    )
    op.drop_index("ix_orders_snapshot_state_created", table_name="orders")
    op.drop_constraint("ck_order_commercial_snapshot", "orders", type_="check")
    op.drop_column("orders", "snapshot_quarantine_reason")
    op.drop_column("orders", "snapshot_state")
    op.drop_column("orders", "total_amount_snapshot")
    op.drop_column("orders", "fee_amount")
    op.drop_column("orders", "tax_amount")
    op.drop_column("orders", "unit_price_amount")
    op.drop_column("orders", "currency_snapshot")
    op.drop_column("orders", "variant_price_label_snapshot")
    op.drop_column("orders", "variant_duration_snapshot")
    op.drop_column("orders", "product_brand_snapshot")
    op.drop_column("orders", "product_title_snapshot")
