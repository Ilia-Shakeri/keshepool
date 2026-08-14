import asyncio
import os
from datetime import timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, TelegramUpdateInbox, utcnow
from app.services.telegram_inbox_service import (
    MAX_ATTEMPTS_ERROR,
    claim_updates,
    enqueue_update,
    mark_update_done,
    mark_update_failed,
    renew_update_claim,
)


RUN_POSTGRES = os.environ.get("KESHEPOOL_RUN_POSTGRES_TESTS") == "1"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES or not TEST_DATABASE_URL,
    reason="Set KESHEPOOL_RUN_POSTGRES_TESTS=1 with a disposable TEST_DATABASE_URL.",
)


def _assert_disposable_database():
    database_name = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database_name.lower():
        raise AssertionError("TEST_DATABASE_URL database name must contain 'test'.")


async def _claim_one(sessions, *, max_attempts: int):
    async with sessions() as session:
        items = await claim_updates(
            session,
            limit=1,
            stale_after_seconds=30,
            max_attempts=max_attempts,
        )
        return items[0] if items else None


async def _age_claim(sessions, inbox_id: int):
    async with sessions() as session:
        await session.execute(
            update(TelegramUpdateInbox)
            .where(TelegramUpdateInbox.id == inbox_id)
            .values(locked_at=utcnow() - timedelta(minutes=2))
        )
        await session.commit()


def test_real_postgres_claim_fence_attempt_cap_and_payload_erasure():
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
                await connection.run_sync(Base.metadata.create_all)

            async with sessions() as session:
                assert await enqueue_update(
                    session,
                    bot_type="main",
                    update_id=880001,
                    payload={"update_id": 880001, "message": {"text": "secret"}},
                )
            first = await _claim_one(sessions, max_attempts=2)
            assert first is not None
            first_token = first.claim_token
            await _age_claim(sessions, first.id)
            second = await _claim_one(sessions, max_attempts=2)
            assert second is not None
            second_token = second.claim_token
            assert first_token != second_token

            async with sessions() as session:
                stale_renewed = await renew_update_claim(
                    session,
                    first.id,
                    claim_token=first_token,
                )
            async with sessions() as session:
                stale_done = await mark_update_done(
                    session,
                    first.id,
                    claim_token=first_token,
                )
            async with sessions() as session:
                current_done = await mark_update_done(
                    session,
                    second.id,
                    claim_token=second_token,
                )

            async with sessions() as session:
                done_row = await session.scalar(
                    select(TelegramUpdateInbox).where(
                        TelegramUpdateInbox.id == second.id
                    )
                )

            async with sessions() as session:
                assert await enqueue_update(
                    session,
                    bot_type="admin",
                    update_id=880002,
                    payload={"update_id": 880002, "callback_query": {"data": "secret"}},
                )
            terminal_claim = await _claim_one(sessions, max_attempts=1)
            assert terminal_claim is not None
            async with sessions() as session:
                terminal_saved = await mark_update_failed(
                    session,
                    terminal_claim.id,
                    claim_token=terminal_claim.claim_token,
                    max_attempts=1,
                    retry_delay_seconds=1,
                    error_class="RuntimeError",
                )
            async with sessions() as session:
                terminal_row = await session.scalar(
                    select(TelegramUpdateInbox).where(
                        TelegramUpdateInbox.id == terminal_claim.id
                    )
                )

            async with sessions() as session:
                assert await enqueue_update(
                    session,
                    bot_type="main",
                    update_id=880003,
                    payload={"update_id": 880003, "message": {"text": "secret"}},
                )
            crashed_claim = await _claim_one(sessions, max_attempts=1)
            assert crashed_claim is not None
            await _age_claim(sessions, crashed_claim.id)
            exhausted_reclaim = await _claim_one(sessions, max_attempts=1)
            async with sessions() as session:
                exhausted_row = await session.scalar(
                    select(TelegramUpdateInbox).where(
                        TelegramUpdateInbox.id == crashed_claim.id
                    )
                )

            return (
                stale_renewed,
                stale_done,
                current_done,
                done_row,
                terminal_saved,
                terminal_row,
                exhausted_reclaim,
                exhausted_row,
            )
        finally:
            await engine.dispose()

    (
        stale_renewed,
        stale_done,
        current_done,
        done_row,
        terminal_saved,
        terminal_row,
        exhausted_reclaim,
        exhausted_row,
    ) = asyncio.run(scenario())

    assert stale_renewed is False
    assert stale_done is False
    assert current_done is True
    assert done_row.status == "done"
    assert done_row.payload == {}
    assert done_row.claim_token is None
    assert terminal_saved is True
    assert terminal_row.status == "failed"
    assert terminal_row.payload == {}
    assert terminal_row.claim_token is None
    assert exhausted_reclaim is None
    assert exhausted_row.status == "failed"
    assert exhausted_row.payload == {}
    assert exhausted_row.last_error == MAX_ATTEMPTS_ERROR
