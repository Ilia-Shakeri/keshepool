import asyncio
import importlib.util
import os
from pathlib import Path

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, User
from app.services.user_service import ensure_user_from_telegram_init


RUN_POSTGRES = os.environ.get("KESHEPOOL_RUN_POSTGRES_TESTS") == "1"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES or not TEST_DATABASE_URL,
    reason="Set KESHEPOOL_RUN_POSTGRES_TESTS=1 with a disposable TEST_DATABASE_URL.",
)

CODE_A = "0123456789abcdef0123456789abcdef"
CODE_B = "fedcba9876543210fedcba9876543210"


def _assert_disposable_database():
    database_name = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database_name.lower():
        raise AssertionError("TEST_DATABASE_URL database name must contain 'test'.")


def _migration_module():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "013_opaque_referral_codes.py"
    )
    spec = importlib.util.spec_from_file_location("migration_013_postgres", migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_real_postgres_referral_attribution_has_one_winner_and_cannot_change():
    _assert_disposable_database()
    migration = _migration_module()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text("DROP FUNCTION IF EXISTS keshepool_protect_user_referrer_id() CASCADE")
                )
                await connection.run_sync(Base.metadata.drop_all)
                await connection.run_sync(Base.metadata.create_all)
                await connection.execute(text(migration._PROTECT_REFERRER_FUNCTION_SQL))
                await connection.execute(text(migration._PROTECT_REFERRER_TRIGGER_SQL))

            async with sessions() as session:
                first = User(
                    telegram_id="100",
                    first_name="First",
                    referral_code=CODE_A,
                )
                second = User(
                    telegram_id="101",
                    first_name="Second",
                    referral_code=CODE_B,
                )
                session.add_all([first, second])
                await session.commit()
                first_id = first.id
                second_id = second.id

            telegram_data = {
                "user": {
                    "id": 200,
                    "first_name": "Invitee",
                    "is_premium": False,
                }
            }

            async def bootstrap(code):
                async with sessions() as session:
                    return await ensure_user_from_telegram_init(
                        session,
                        telegram_data,
                        referral_code=code,
                    )

            users = await asyncio.gather(bootstrap(CODE_A), bootstrap(CODE_B))
            async with sessions() as session:
                invitee = (
                    await session.execute(select(User).where(User.telegram_id == "200"))
                ).scalar_one()
                winner = invitee.referrer_id

            async with sessions() as session:
                await ensure_user_from_telegram_init(
                    session,
                    telegram_data,
                    referral_code=CODE_B if winner == first_id else CODE_A,
                )
                unchanged = (
                    await session.execute(select(User).where(User.telegram_id == "200"))
                ).scalar_one()

            async with sessions() as session:
                with pytest.raises(DBAPIError):
                    await session.execute(
                        update(User)
                        .where(User.telegram_id == "200")
                        .values(referrer_id=second_id if winner == first_id else first_id)
                    )
                    await session.commit()
                await session.rollback()

            return users, winner, unchanged.referrer_id, {first_id, second_id}
        finally:
            await engine.dispose()

    users, winner, unchanged, valid_referrers = asyncio.run(scenario())
    assert len({user.id for user in users}) == 1
    assert winner in valid_referrers
    assert unchanged == winner
