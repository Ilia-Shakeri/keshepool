"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-27

NOTE: For databases that were already bootstrapped via SQLAlchemy's create_all()
(i.e. the original production deployment), skip applying this migration and
mark it as already applied:

    alembic stamp 001

Then run the remaining migrations normally:

    alembic upgrade head
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── enum types ────────────────────────────────────────────────────────────
    itemstatus = sa.Enum(
        "available", "reserved", "assigned", "expired", "disabled",
        name="itemstatus",
    )
    transactiontype = sa.Enum(
        "deposit_irr", "deposit_crypto", "purchase", "cashout", "refund", "referral_bonus",
        name="transactiontype",
    )
    transactionstatus = sa.Enum(
        "pending", "success", "failed",
        name="transactionstatus",
    )
    orderstatus = sa.Enum(
        "active", "expired", "cancelled", "refunded",
        name="orderstatus",
    )

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("language_code", sa.String(), nullable=True),
        sa.Column("photo_url", sa.String(), nullable=True),
        sa.Column("is_premium", sa.Boolean(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("referrer_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    # ── wallets ───────────────────────────────────────────────────────────────
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_wallet_user_id"),
    )
    op.create_index("ix_wallets_id", "wallets", ["id"])

    # ── transactions ──────────────────────────────────────────────────────────
    # NOTE: currency and gateway columns are added in migration 002.
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("type", transactiontype, nullable=False),
        sa.Column("status", transactionstatus, nullable=False),
        sa.Column("reference_id", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_id", "transactions", ["id"])
    op.create_index("ix_transactions_reference_id", "transactions", ["reference_id"])
    op.create_index("ix_transactions_wallet_created", "transactions", ["wallet_id", "created_at"])

    # ── products ──────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=False),
        sa.Column("subtitle", sa.String(), nullable=True),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("asset_url", sa.String(), nullable=True),
        sa.Column("gradient", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_id", "products", ["id"])
    op.create_index("ix_products_category", "products", ["category"])

    # ── product_variants ──────────────────────────────────────────────────────
    op.create_table(
        "product_variants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("duration", sa.String(), nullable=False),
        sa.Column("price_label", sa.String(), nullable=False),
        sa.Column("raw_price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_variants_id", "product_variants", ["id"])
    op.create_index("ix_product_variants_product_id", "product_variants", ["product_id"])

    # ── inventory_items ───────────────────────────────────────────────────────
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("variant_id", sa.String(), nullable=False),
        sa.Column("credentials", sa.Text(), nullable=False),
        sa.Column("status", itemstatus, nullable=False),
        sa.Column("assigned_to_user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "variant_id", "credentials", name="uq_inventory_unique_credentials"),
    )
    op.create_index("ix_inventory_items_id", "inventory_items", ["id"])
    op.create_index("ix_inventory_items_product_id", "inventory_items", ["product_id"])
    op.create_index("ix_inventory_items_variant_id", "inventory_items", ["variant_id"])
    op.create_index("ix_inventory_items_status", "inventory_items", ["status"])
    op.create_index("ix_inventory_available", "inventory_items", ["product_id", "variant_id", "status"])

    # ── orders ────────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("variant_id", sa.String(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", orderstatus, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["variant_id"], ["product_variants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inventory_item_id", name="uq_order_inventory_item_id"),
    )
    op.create_index("ix_orders_id", "orders", ["id"])
    op.create_index("ix_orders_public_id", "orders", ["public_id"], unique=True)
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_index("ix_orders_status", "orders")
    op.drop_index("ix_orders_user_id", "orders")
    op.drop_index("ix_orders_public_id", "orders")
    op.drop_index("ix_orders_id", "orders")
    op.drop_table("orders")
    op.drop_index("ix_inventory_available", "inventory_items")
    op.drop_index("ix_inventory_items_status", "inventory_items")
    op.drop_index("ix_inventory_items_variant_id", "inventory_items")
    op.drop_index("ix_inventory_items_product_id", "inventory_items")
    op.drop_index("ix_inventory_items_id", "inventory_items")
    op.drop_table("inventory_items")
    op.drop_index("ix_product_variants_product_id", "product_variants")
    op.drop_index("ix_product_variants_id", "product_variants")
    op.drop_table("product_variants")
    op.drop_index("ix_products_category", "products")
    op.drop_index("ix_products_id", "products")
    op.drop_table("products")
    op.drop_index("ix_transactions_wallet_created", "transactions")
    op.drop_index("ix_transactions_reference_id", "transactions")
    op.drop_index("ix_transactions_id", "transactions")
    op.drop_table("transactions")
    op.drop_index("ix_wallets_id", "wallets")
    op.drop_table("wallets")
    op.drop_index("ix_users_telegram_id", "users")
    op.drop_index("ix_users_id", "users")
    op.drop_table("users")

    sa.Enum(name="orderstatus").drop(op.get_bind())
    sa.Enum(name="transactionstatus").drop(op.get_bind())
    sa.Enum(name="transactiontype").drop(op.get_bind())
    sa.Enum(name="itemstatus").drop(op.get_bind())
