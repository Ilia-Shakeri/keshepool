import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import users
from app.models import (
    Base,
    CredentialRevealEvent,
    InventoryItem,
    ItemStatus,
    Order,
    OrderStatus,
    Product,
    ProductVariant,
    User,
)
from app.services.cache_service import RateLimitDecision


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


def _request(request_id: str) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/orders/reveal-race/reveal-credential",
            "headers": [],
        }
    )
    request.state.request_id = request_id
    return request


def test_real_postgres_reveal_limit_has_one_concurrent_winner(monkeypatch):
    _assert_disposable_database()
    monkeypatch.setattr(users.settings, "CREDENTIAL_REVEAL_MAX_PER_ORDER", 1)
    monkeypatch.setattr(
        users,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=1,
                backend_available=True,
            )
        ),
    )

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
                await connection.run_sync(Base.metadata.create_all)

            async with sessions() as session:
                user = User(telegram_id="700", first_name="Reveal")
                product = Product(
                    id="reveal-product",
                    title="Reveal Product",
                    brand="Reveal Brand",
                    category="tools",
                )
                variant = ProductVariant(
                    id="reveal-variant",
                    product_id=product.id,
                    duration="one month",
                    price_label="100",
                    raw_price=100,
                )
                session.add_all([user, product, variant])
                await session.flush()
                item = InventoryItem(
                    product_id=product.id,
                    variant_id=variant.id,
                    credentials="fixture-race-value",
                    status=ItemStatus.ASSIGNED,
                    assigned_to_user_id=user.id,
                )
                session.add(item)
                await session.flush()
                order = Order(
                    public_id="KP-REVEAL-RACE",
                    user_id=user.id,
                    product_id=product.id,
                    variant_id=variant.id,
                    inventory_item_id=item.id,
                    total_amount=100,
                    product_title_snapshot="Reveal Product",
                    product_brand_snapshot="Reveal Brand",
                    variant_duration_snapshot="one month",
                    variant_price_label_snapshot="100",
                    currency_snapshot="IRR",
                    unit_price_amount=100,
                    tax_amount=0,
                    fee_amount=0,
                    total_amount_snapshot=100,
                    snapshot_state="complete",
                    snapshot_quarantine_reason=None,
                    status=OrderStatus.ACTIVE,
                )
                session.add(order)
                await session.commit()
                user_ref = SimpleNamespace(id=user.id, telegram_id=user.telegram_id)

            async def reveal(request_id: str):
                async with sessions() as session:
                    try:
                        result = await users.reveal_order_credential(
                            request=_request(request_id),
                            response=Response(),
                            public_id="KP-REVEAL-RACE",
                            user=user_ref,
                            db=session,
                        )
                        return result.credential
                    except HTTPException as exc:
                        return exc.status_code

            outcomes = await asyncio.gather(reveal("race-1"), reveal("race-2"))
            async with sessions() as session:
                stored_order = await session.scalar(
                    select(Order).where(Order.public_id == "KP-REVEAL-RACE")
                )
                events = (
                    await session.execute(
                        select(CredentialRevealEvent).order_by(CredentialRevealEvent.id)
                    )
                ).scalars().all()
                return outcomes, stored_order.credential_reveal_count, events
        finally:
            await engine.dispose()

    outcomes, reveal_count, events = asyncio.run(scenario())
    assert sorted(str(outcome) for outcome in outcomes) == ["409", "fixture-race-value"]
    assert reveal_count == 1
    assert sorted(event.outcome for event in events) == ["allowed", "denied_limit"]
    assert all(not hasattr(event, "credential") for event in events)
