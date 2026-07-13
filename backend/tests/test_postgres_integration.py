import asyncio
import os
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import products as products_api
from app.models import (
    Base,
    InventoryItem,
    ItemStatus,
    Order,
    Product,
    ProductVariant,
    User,
    Wallet,
)
from app.services import cache_service
from app.services.catalog_service import (
    VariantOwnershipError,
    set_product_active,
    upsert_product,
)
from app.services.inventory_service import fulfill_wallet_order
from app.services.user_service import ensure_user_from_telegram_init


RUN_POSTGRES = os.environ.get("KESHEPOOL_RUN_POSTGRES_TESTS") == "1"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES or not TEST_DATABASE_URL,
    reason="Set KESHEPOOL_RUN_POSTGRES_TESTS=1 with a disposable TEST_DATABASE_URL.",
)


class MemoryRedis:
    def __init__(self):
        self.data = {}
        self.counts = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def setex(self, key, ttl, value):
        self.data[key] = value
        return True

    async def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)
        return len(keys)

    async def eval(self, script, number_of_keys, key, *args):
        if "incr" in script:
            self.counts[key] = self.counts.get(key, 0) + 1
            return self.counts[key]
        token = args[0]
        if self.data.get(key) == token:
            self.data.pop(key, None)
            return 1
        return 0


def _assert_disposable_database():
    database_name = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database_name.lower():
        raise AssertionError("TEST_DATABASE_URL database name must contain 'test'.")


async def _reset_database(engine):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


async def _seed_checkout_case(sessions):
    async with sessions() as session:
        user = User(telegram_id="checkout-user", first_name="Checkout")
        session.add(user)
        await session.flush()
        session.add(Wallet(user_id=user.id, balance=Decimal("1000.00")))
        session.add(
            Product(
                id="checkout-product",
                title="Checkout Product",
                brand="Checkout Brand",
                category="tools",
                is_active=True,
            )
        )
        session.add(
            ProductVariant(
                id="checkout-variant",
                product_id="checkout-product",
                duration="1 month",
                price_label="100",
                raw_price=Decimal("100.00"),
                is_active=True,
            )
        )
        item = InventoryItem(
            product_id="checkout-product",
            variant_id="checkout-variant",
            credentials="single-live-credential",
            status=ItemStatus.AVAILABLE,
        )
        session.add(item)
        await session.commit()
        return user.id, item.id


async def _checkout_once(sessions, user_id: int, idempotency_key: str):
    async with sessions() as session:
        return await fulfill_wallet_order(
            session,
            SimpleNamespace(id=user_id),
            "checkout-product",
            "checkout-variant",
            idempotency_key=idempotency_key,
        )


async def _checkout_state(sessions, user_id: int, item_id: int):
    async with sessions() as session:
        orders = (await session.execute(select(Order))).scalars().all()
        wallet_balance = await session.scalar(
            select(Wallet.balance).where(Wallet.user_id == user_id)
        )
        item = await session.get(InventoryItem, item_id)
        return orders, wallet_balance, item


def test_real_postgres_concurrent_bootstrap_creates_one_user_and_wallet():
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            telegram_data = {"user": {"id": 424242, "first_name": "Concurrent"}}

            async def bootstrap_once():
                async with sessions() as session:
                    return await ensure_user_from_telegram_init(session, telegram_data)

            users = await asyncio.gather(*(bootstrap_once() for _ in range(12)))
            async with sessions() as session:
                user_count = await session.scalar(select(func.count(User.id)))
                wallet_count = await session.scalar(select(func.count(Wallet.id)))
            return users, user_count, wallet_count
        finally:
            await engine.dispose()

    users, user_count, wallet_count = asyncio.run(scenario())
    assert user_count == 1
    assert wallet_count == 1
    assert len({user.id for user in users}) == 1


def test_real_postgres_same_checkout_key_returns_one_order_and_one_sale():
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            user_id, item_id = await _seed_checkout_case(sessions)
            first, second = await asyncio.gather(
                _checkout_once(sessions, user_id, "same-checkout-key"),
                _checkout_once(sessions, user_id, "same-checkout-key"),
            )
            state = await _checkout_state(sessions, user_id, item_id)
            return first, second, user_id, state
        finally:
            await engine.dispose()

    first, second, user_id, (orders, wallet_balance, item) = asyncio.run(scenario())
    assert first.id == second.id
    assert len(orders) == 1
    assert wallet_balance == Decimal("900.00")
    assert item.status == ItemStatus.ASSIGNED
    assert item.assigned_to_user_id == user_id


def test_real_postgres_distinct_checkout_keys_race_one_stock_one_sale():
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            user_id, item_id = await _seed_checkout_case(sessions)
            results = await asyncio.gather(
                _checkout_once(sessions, user_id, "checkout-key-one"),
                _checkout_once(sessions, user_id, "checkout-key-two"),
                return_exceptions=True,
            )
            state = await _checkout_state(sessions, user_id, item_id)
            return results, user_id, state
        finally:
            await engine.dispose()

    results, user_id, (orders, wallet_balance, item) = asyncio.run(scenario())
    successes = [result for result in results if isinstance(result, Order)]
    failures = [result for result in results if isinstance(result, HTTPException)]
    assert len(successes) == 1
    assert len(failures) == 1
    assert failures[0].status_code == 409
    assert len(orders) == 1
    assert wallet_balance == Decimal("900.00")
    assert item.status == ItemStatus.ASSIGNED
    assert item.assigned_to_user_id == user_id


def test_real_postgres_checkout_retry_after_committed_reply_loss_returns_same_order():
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            user_id, item_id = await _seed_checkout_case(sessions)

            async with sessions() as session:
                with patch.object(
                    session,
                    "refresh",
                    AsyncMock(side_effect=ConnectionError("reply lost after commit")),
                ):
                    with pytest.raises(HTTPException) as first_error:
                        await fulfill_wallet_order(
                            session,
                            SimpleNamespace(id=user_id),
                            "checkout-product",
                            "checkout-variant",
                            idempotency_key="reply-loss-key",
                        )

            retry = await _checkout_once(sessions, user_id, "reply-loss-key")
            state = await _checkout_state(sessions, user_id, item_id)
            return first_error.value, retry, user_id, state
        finally:
            await engine.dispose()

    first_error, retry, user_id, (orders, wallet_balance, item) = asyncio.run(scenario())
    assert first_error.status_code == 500
    assert len(orders) == 1
    assert retry.id == orders[0].id
    assert wallet_balance == Decimal("900.00")
    assert item.status == ItemStatus.ASSIGNED
    assert item.assigned_to_user_id == user_id


def test_admin_mutation_is_visible_through_public_endpoint_and_cache(monkeypatch):
    _assert_disposable_database()
    memory_redis = MemoryRedis()
    monkeypatch.setattr(cache_service, "redis_client", memory_redis)

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            await _reset_database(engine)
            payload = {
                "id": "sync-product",
                "title": "Synced Product",
                "brand": "Synced Brand",
                "category": "tools",
                "variants": [
                    {
                        "id": "sync-variant",
                        "duration": "1 month",
                        "rawPrice": 100_000,
                        "credentials": ["credential-one", "credential-one"],
                    }
                ],
            }
            async with sessions() as session:
                mutation = await upsert_product(
                    session,
                    payload,
                    replace_variants=True,
                )
            test_user = User(id=999, telegram_id="999")
            async with sessions() as session:
                visible = await products_api.get_all_products(
                    request=None,
                    user=test_user,
                    db=session,
                )

            async with sessions() as session:
                await set_product_active(session, "sync-product", False)
            async with sessions() as session:
                hidden = await products_api.get_all_products(
                    request=None,
                    user=test_user,
                    db=session,
                )

            async with sessions() as session:
                await set_product_active(session, "sync-product", True)
            async with sessions() as session:
                visible_again = await products_api.get_all_products(
                    request=None,
                    user=test_user,
                    db=session,
                )

            async with sessions() as session:
                with pytest.raises(VariantOwnershipError):
                    await upsert_product(
                        session,
                        {
                            "id": "other-product",
                            "title": "Other",
                            "brand": "Other",
                            "category": "tools",
                            "variants": [
                                {
                                    "id": "sync-variant",
                                    "duration": "1 month",
                                    "rawPrice": 1,
                                }
                            ],
                        },
                        replace_variants=True,
                    )
                    await session.rollback()
            return mutation, visible, hidden, visible_again
        finally:
            await engine.dispose()

    mutation, visible, hidden, visible_again = asyncio.run(scenario())
    assert mutation.inserted_stock_count == 1
    assert mutation.duplicate_stock_count == 1
    assert visible[0]["id"] == "sync-product"
    assert visible[0]["variants"][0]["stockCount"] == 1
    assert hidden == []
    assert visible_again[0]["id"] == "sync-product"
