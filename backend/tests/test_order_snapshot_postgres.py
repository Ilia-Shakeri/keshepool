import asyncio
import os
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import (
    Base,
    InventoryItem,
    ItemStatus,
    Order,
    Product,
    ProductVariant,
    User,
    Wallet,
    utcnow,
)
from app.services.inventory_service import fulfill_wallet_order


RUN_POSTGRES = os.environ.get("KESHEPOOL_RUN_POSTGRES_TESTS") == "1"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES or not TEST_DATABASE_URL,
    reason="Set KESHEPOOL_RUN_POSTGRES_TESTS=1 with a disposable TEST_DATABASE_URL.",
)


def _assert_disposable_database() -> None:
    database_name = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database_name.lower():
        raise AssertionError("TEST_DATABASE_URL database name must contain 'test'.")


async def _reset_database(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


async def _seed_fifo_case(sessions):
    now = utcnow()
    async with sessions() as session:
        users = [
            User(telegram_id="snapshot-user-one", first_name="One"),
            User(telegram_id="snapshot-user-two", first_name="Two"),
        ]
        session.add_all(users)
        await session.flush()
        session.add_all(
            [
                Wallet(user_id=users[0].id, balance=Decimal("1000.00")),
                Wallet(user_id=users[1].id, balance=Decimal("1000.00")),
                Product(
                    id="snapshot-product",
                    title="Original Product",
                    brand="Original Brand",
                    category="tools",
                    is_active=True,
                ),
            ]
        )
        session.add(
            ProductVariant(
                id="snapshot-variant",
                product_id="snapshot-product",
                duration="Original Duration",
                price_label="100 Toman",
                raw_price=Decimal("100.00"),
                is_active=True,
            )
        )
        await session.flush()
        items = [
            InventoryItem(
                product_id="snapshot-product",
                variant_id="snapshot-variant",
                credentials="fifo-first",
                status=ItemStatus.AVAILABLE,
                expires_at=now + timedelta(days=1),
                created_at=now - timedelta(days=1),
            ),
            InventoryItem(
                product_id="snapshot-product",
                variant_id="snapshot-variant",
                credentials="fifo-second",
                status=ItemStatus.AVAILABLE,
                expires_at=now + timedelta(days=2),
                created_at=now - timedelta(days=3),
            ),
            InventoryItem(
                product_id="snapshot-product",
                variant_id="snapshot-variant",
                credentials="fifo-no-expiry",
                status=ItemStatus.AVAILABLE,
                expires_at=None,
                created_at=now - timedelta(days=10),
            ),
        ]
        session.add_all(items)
        await session.commit()
        return [user.id for user in users], [item.id for item in items]


def test_real_postgres_concurrent_fifo_and_catalog_snapshot_stability() -> None:
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            user_ids, item_ids = await _seed_fifo_case(sessions)

            async def checkout(user_id: int, key: str):
                async with sessions() as session:
                    return await fulfill_wallet_order(
                        session,
                        SimpleNamespace(id=user_id),
                        "snapshot-product",
                        "snapshot-variant",
                        idempotency_key=key,
                    )

            orders = await asyncio.gather(
                checkout(user_ids[0], "snapshot-fifo-one"),
                checkout(user_ids[1], "snapshot-fifo-two"),
            )
            async with sessions() as session:
                product = await session.get(Product, "snapshot-product")
                variant = await session.get(ProductVariant, "snapshot-variant")
                product.title = "Changed Product"
                product.brand = "Changed Brand"
                product.is_active = False
                variant.duration = "Changed Duration"
                variant.price_label = "900 Toman"
                variant.raw_price = Decimal("900.00")
                variant.is_active = False
                await session.commit()

            async with sessions() as session:
                stored = (
                    await session.execute(select(Order).order_by(Order.id.asc()))
                ).scalars().all()
                assigned_ids = {
                    int(value)
                    for value in (
                        await session.execute(
                            select(Order.inventory_item_id).order_by(Order.id.asc())
                        )
                    ).scalars().all()
                }
                remaining = await session.scalar(
                    select(func.count(InventoryItem.id)).where(
                        InventoryItem.status == ItemStatus.AVAILABLE
                    )
                )
            return orders, stored, assigned_ids, item_ids, int(remaining or 0)
        finally:
            await engine.dispose()

    orders, stored, assigned_ids, item_ids, remaining = asyncio.run(scenario())
    assert len(orders) == 2
    assert assigned_ids == set(item_ids[:2])
    assert remaining == 1
    assert all(order.product_title_snapshot == "Original Product" for order in stored)
    assert all(order.product_brand_snapshot == "Original Brand" for order in stored)
    assert all(order.variant_duration_snapshot == "Original Duration" for order in stored)
    assert all(order.unit_price_amount == Decimal("100.00") for order in stored)
    assert all(order.total_amount_snapshot == Decimal("100.00") for order in stored)


def test_real_postgres_visibility_change_serializes_before_checkout() -> None:
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            user_ids, item_ids = await _seed_fifo_case(sessions)
            async with sessions() as mutation_session:
                product = await mutation_session.scalar(
                    select(Product)
                    .where(Product.id == "snapshot-product")
                    .with_for_update()
                )
                product.is_active = False
                checkout_task = asyncio.create_task(
                    _checkout_while_catalog_locked(sessions, user_ids[0])
                )
                await asyncio.sleep(0)
                await mutation_session.commit()
                result = await checkout_task
            async with sessions() as session:
                order_count = await session.scalar(select(func.count(Order.id)))
                item = await session.get(InventoryItem, item_ids[0])
                wallet_balance = await session.scalar(
                    select(Wallet.balance).where(Wallet.user_id == user_ids[0])
                )
            return result, int(order_count or 0), item.status, wallet_balance
        finally:
            await engine.dispose()

    result, order_count, item_status, wallet_balance = asyncio.run(scenario())
    assert isinstance(result, HTTPException)
    assert result.status_code == 404
    assert order_count == 0
    assert item_status == ItemStatus.AVAILABLE
    assert wallet_balance == Decimal("1000.00")


def test_real_postgres_price_change_serializes_before_snapshot() -> None:
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            user_ids, _ = await _seed_fifo_case(sessions)
            async with sessions() as mutation_session:
                variant = await mutation_session.scalar(
                    select(ProductVariant)
                    .where(ProductVariant.id == "snapshot-variant")
                    .with_for_update()
                )
                variant.raw_price = Decimal("175.00")
                variant.duration = "Changed Before Sale"
                variant.price_label = "175 Toman"
                checkout_task = asyncio.create_task(
                    _checkout_for_price_race(sessions, user_ids[0])
                )
                await asyncio.sleep(0)
                await mutation_session.commit()
                order = await checkout_task
            async with sessions() as session:
                wallet_balance = await session.scalar(
                    select(Wallet.balance).where(Wallet.user_id == user_ids[0])
                )
            return order, wallet_balance
        finally:
            await engine.dispose()

    order, wallet_balance = asyncio.run(scenario())
    assert order.unit_price_amount == Decimal("175.00")
    assert order.total_amount_snapshot == Decimal("175.00")
    assert order.variant_duration_snapshot == "Changed Before Sale"
    assert order.variant_price_label_snapshot == "175"
    assert wallet_balance == Decimal("825.00")


async def _checkout_while_catalog_locked(sessions, user_id: int):
    async with sessions() as session:
        try:
            return await fulfill_wallet_order(
                session,
                SimpleNamespace(id=user_id),
                "snapshot-product",
                "snapshot-variant",
                idempotency_key="visibility-race",
            )
        except HTTPException as exc:
            return exc


async def _checkout_for_price_race(sessions, user_id: int):
    async with sessions() as session:
        return await fulfill_wallet_order(
            session,
            SimpleNamespace(id=user_id),
            "snapshot-product",
            "snapshot-variant",
            idempotency_key="price-race",
        )
