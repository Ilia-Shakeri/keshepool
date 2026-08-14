import asyncio
import os
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models import (
    AdminAuditLog,
    Base,
    UsdtRateOverride,
    UsdtRateOverrideVersion,
)
from app.services import rate_service


RUN_POSTGRES = os.environ.get("KESHEPOOL_RUN_POSTGRES_TESTS") == "1"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES or not TEST_DATABASE_URL,
    reason="Set KESHEPOOL_RUN_POSTGRES_TESTS=1 with a disposable TEST_DATABASE_URL.",
)


def test_concurrent_rate_writes_get_distinct_audit_versions():
    database_name = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database_name.lower():
        raise AssertionError("TEST_DATABASE_URL database name must contain 'test'.")

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
                await connection.run_sync(Base.metadata.create_all)
            with patch.object(rate_service, "AsyncSessionLocal", sessions):
                with patch.object(settings, "OPERATIONS_RATE_DB_ENABLED", True):
                    await asyncio.gather(
                        rate_service._commit_db_override(
                            rate=91_000,
                            actor_telegram_id="100",
                            change_source="postgres_test",
                        ),
                        rate_service._commit_db_override(
                            rate=92_000,
                            actor_telegram_id="200",
                            change_source="postgres_test",
                        ),
                    )
            async with sessions() as session:
                current = await session.get(
                    UsdtRateOverride,
                    rate_service.RATE_OVERRIDE_SINGLETON_ID,
                )
                history = (
                    await session.execute(
                        select(UsdtRateOverrideVersion).order_by(
                            UsdtRateOverrideVersion.version
                        )
                    )
                ).scalars().all()
                audits = (await session.execute(select(AdminAuditLog))).scalars().all()
            return current, history, audits
        finally:
            await engine.dispose()

    current, history, audits = asyncio.run(scenario())
    assert current.version == 2
    assert [row.version for row in history] == [1, 2]
    assert {row.changed_by_telegram_id for row in history} == {"100", "200"}
    assert {row.actor_telegram_id for row in audits} == {"100", "200"}


def test_rolled_back_rate_change_leaves_no_source_version_or_audit():
    database_name = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database_name.lower():
        raise AssertionError("TEST_DATABASE_URL database name must contain 'test'.")

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
                await connection.run_sync(Base.metadata.create_all)
            async with sessions() as session:
                with patch.object(settings, "OPERATIONS_RATE_DB_ENABLED", True):
                    await rate_service.apply_usdt_rate_override_in_session(
                        session,
                        rate=93_000,
                        actor_telegram_id="300",
                        change_source="postgres_test",
                    )
                await session.rollback()
            async with sessions() as session:
                current = await session.get(
                    UsdtRateOverride,
                    rate_service.RATE_OVERRIDE_SINGLETON_ID,
                )
                versions = (
                    await session.execute(select(UsdtRateOverrideVersion))
                ).scalars().all()
                audits = (await session.execute(select(AdminAuditLog))).scalars().all()
            return current, versions, audits
        finally:
            await engine.dispose()

    current, versions, audits = asyncio.run(scenario())
    assert current is None
    assert versions == []
    assert audits == []
