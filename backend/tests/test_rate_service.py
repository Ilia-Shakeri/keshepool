import asyncio
import importlib.util
import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings, settings
from app.models import AdminAuditLog, UsdtRateOverrideVersion
from app.services import cache_service, rate_service
from app.services.rate_service import RateOverrideState


class MemoryRedis:
    def __init__(self):
        self.data: dict[str, str] = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, **kwargs):
        self.data[key] = str(value)
        return True

    async def setex(self, key, ttl, value):
        self.data[key] = str(value)
        return True

    async def delete(self, *keys):
        removed = 0
        for key in keys:
            removed += int(self.data.pop(key, None) is not None)
        return removed


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def memory_redis(monkeypatch):
    memory = MemoryRedis()
    monkeypatch.setattr(rate_service, "redis_client", memory)
    monkeypatch.setattr(cache_service, "redis_client", memory)
    return memory


def test_legacy_mode_keeps_redis_contract(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", False)
    db_write = AsyncMock(side_effect=AssertionError("database path must stay off"))
    monkeypatch.setattr(rate_service, "_commit_db_override", db_write)

    run(rate_service.set_usdt_rate(91_000))
    assert run(rate_service.get_usdt_rate()) == Decimal("91000")
    run(rate_service.clear_usdt_rate_override())

    assert rate_service.USDT_RATE_KEY not in memory_redis.data
    db_write.assert_not_awaited()


def test_durable_set_writes_database_then_both_caches(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    db_write = AsyncMock(
        return_value=RateOverrideState(
            exists=True,
            is_active=True,
            version=3,
            rate=Decimal("92000"),
        )
    )
    monkeypatch.setattr(rate_service, "_commit_db_override", db_write)

    run(
        rate_service.set_usdt_rate(
            92_000,
            actor_telegram_id=123456,
            change_source="dual_approval",
        )
    )

    db_write.assert_awaited_once_with(
        rate=92_000,
        actor_telegram_id=123456,
        change_source="dual_approval",
    )
    assert memory_redis.data[rate_service.USDT_RATE_KEY] == "92000"
    cached = json.loads(memory_redis.data[rate_service.USDT_RATE_DB_CACHE_KEY])
    assert cached == {"version": 3, "isActive": True, "rate": "92000"}


def test_durable_clear_records_version_and_removes_legacy_cache(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    memory_redis.data[rate_service.USDT_RATE_KEY] = "91000"
    db_write = AsyncMock(
        return_value=RateOverrideState(exists=True, is_active=False, version=4)
    )
    monkeypatch.setattr(rate_service, "_commit_db_override", db_write)

    run(
        rate_service.clear_usdt_rate_override(
            actor_telegram_id="654321",
            change_source="dual_approval",
        )
    )

    db_write.assert_awaited_once_with(
        rate=None,
        actor_telegram_id="654321",
        change_source="dual_approval",
    )
    assert rate_service.USDT_RATE_KEY not in memory_redis.data
    cached = json.loads(memory_redis.data[rate_service.USDT_RATE_DB_CACHE_KEY])
    assert cached == {"version": 4, "isActive": False, "rate": None}


def test_durable_read_beats_stale_legacy_cache(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    memory_redis.data[rate_service.USDT_RATE_KEY] = "100"
    monkeypatch.setattr(
        rate_service,
        "_load_db_override",
        AsyncMock(
            return_value=RateOverrideState(
                exists=True,
                is_active=True,
                version=8,
                rate=Decimal("93000"),
            )
        ),
    )
    fetch = AsyncMock(side_effect=AssertionError("live source must not run"))
    monkeypatch.setattr(rate_service, "_fetch_live_rate", fetch)

    assert run(rate_service.get_usdt_rate()) == Decimal("93000")
    assert memory_redis.data[rate_service.USDT_RATE_KEY] == "93000"
    fetch.assert_not_awaited()


def test_first_durable_read_imports_valid_legacy_override(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    memory_redis.data[rate_service.USDT_RATE_KEY] = "94000"
    monkeypatch.setattr(
        rate_service,
        "_load_db_override",
        AsyncMock(return_value=RateOverrideState.missing()),
    )
    importer = AsyncMock(
        return_value=RateOverrideState(
            exists=True,
            is_active=True,
            version=1,
            rate=Decimal("94000"),
        )
    )
    monkeypatch.setattr(rate_service, "_import_legacy_override", importer)

    assert run(rate_service.get_usdt_rate()) == Decimal("94000")
    importer.assert_awaited_once_with(Decimal("94000"))


def test_database_outage_uses_only_short_lived_durable_cache(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    memory_redis.data[rate_service.USDT_RATE_KEY] = "100"
    memory_redis.data[rate_service.USDT_RATE_DB_CACHE_KEY] = json.dumps(
        {"version": 5, "isActive": True, "rate": "95000"}
    )
    monkeypatch.setattr(
        rate_service,
        "_load_db_override",
        AsyncMock(side_effect=SQLAlchemyError("database unavailable")),
    )

    assert run(rate_service.get_usdt_rate()) == Decimal("95000")


def test_corrupt_durable_state_drops_both_override_caches(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    memory_redis.data[rate_service.USDT_RATE_KEY] = "999999"
    memory_redis.data[rate_service.USDT_RATE_DB_CACHE_KEY] = json.dumps(
        {"version": 5, "isActive": True, "rate": "999999"}
    )
    memory_redis.data[rate_service.USDT_LIVE_RATE_KEY] = "85000"
    monkeypatch.setattr(
        rate_service,
        "_load_db_override",
        AsyncMock(side_effect=ValueError("bad durable row")),
    )

    assert run(rate_service.get_usdt_rate()) == Decimal("85000")
    assert rate_service.USDT_RATE_KEY not in memory_redis.data
    assert rate_service.USDT_RATE_DB_CACHE_KEY not in memory_redis.data


def test_durable_clear_state_ignores_stale_manual_value(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    memory_redis.data[rate_service.USDT_RATE_KEY] = "999999"
    memory_redis.data[rate_service.USDT_LIVE_RATE_KEY] = "85000"
    monkeypatch.setattr(
        rate_service,
        "_load_db_override",
        AsyncMock(return_value=RateOverrideState(exists=True, is_active=False, version=9)),
    )

    assert run(rate_service.get_usdt_rate()) == Decimal("85000")
    assert rate_service.USDT_RATE_KEY not in memory_redis.data


@pytest.mark.parametrize("rate", [0, -1, True, 1.5, 10**17])
def test_rate_write_rejects_unsafe_values(monkeypatch, memory_redis, rate):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    with pytest.raises(ValueError):
        run(rate_service.set_usdt_rate(rate))


class FakeRateSession:
    def __init__(self, *, version=7, events=None, fail_commit=False):
        self.version = version
        self.events = events if events is not None else []
        self.fail_commit = fail_commit
        self.added = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def scalar(self, statement):
        self.events.append("rate-upsert")
        return self.version

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        self.events.append("flush")

    async def commit(self):
        self.events.append("commit")
        if self.fail_commit:
            raise SQLAlchemyError("commit failed")

    async def rollback(self):
        self.events.append("rollback")


def test_session_rate_change_stages_version_and_actor_audit_without_commit():
    session = FakeRateSession(version=7)
    original_flag = settings.OPERATIONS_RATE_DB_ENABLED
    settings.OPERATIONS_RATE_DB_ENABLED = True
    try:
        state = run(
            rate_service.apply_usdt_rate_override_in_session(
                session,
                rate=96_000,
                actor_telegram_id="123456",
                change_source="dual_approval",
            )
        )
    finally:
        settings.OPERATIONS_RATE_DB_ENABLED = original_flag

    assert state == RateOverrideState(
        exists=True,
        is_active=True,
        version=7,
        rate=Decimal("96000"),
    )
    version_row = next(row for row in session.added if isinstance(row, UsdtRateOverrideVersion))
    audit_row = next(row for row in session.added if isinstance(row, AdminAuditLog))
    assert version_row.version == 7
    assert version_row.changed_by_telegram_id == "123456"
    assert audit_row.action == "exchange_rate.manual_override"
    assert audit_row.actor_telegram_id == "123456"
    assert audit_row.details == {
        "version": 7,
        "source": "dual_approval",
        "rate": 96_000,
    }
    assert "commit" not in session.events


def test_session_rate_change_cannot_bypass_disabled_cutover(monkeypatch):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", False)
    session = FakeRateSession(version=7)

    with pytest.raises(RuntimeError, match="disabled"):
        run(
            rate_service.apply_usdt_rate_override_in_session(
                session,
                rate=96_000,
                actor_telegram_id="123456",
            )
        )

    assert session.events == []
    assert session.added == []


def test_public_durable_write_caches_only_after_commit(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    events = []
    session = FakeRateSession(version=2, events=events)
    monkeypatch.setattr(rate_service, "AsyncSessionLocal", lambda: session)
    original_cache = rate_service.cache_usdt_rate_override

    async def tracked_cache(state):
        events.append("cache")
        await original_cache(state)

    monkeypatch.setattr(rate_service, "cache_usdt_rate_override", tracked_cache)

    run(rate_service.set_usdt_rate(97_000, actor_telegram_id="123456"))

    assert events.index("commit") < events.index("cache")
    assert memory_redis.data[rate_service.USDT_RATE_KEY] == "97000"


def test_failed_commit_never_changes_rate_cache(monkeypatch, memory_redis):
    monkeypatch.setattr(settings, "OPERATIONS_RATE_DB_ENABLED", True)
    memory_redis.data[rate_service.USDT_RATE_KEY] = "85000"
    session = FakeRateSession(version=2, fail_commit=True)
    monkeypatch.setattr(rate_service, "AsyncSessionLocal", lambda: session)

    with pytest.raises(SQLAlchemyError, match="commit failed"):
        run(rate_service.set_usdt_rate(98_000, actor_telegram_id="123456"))

    assert memory_redis.data[rate_service.USDT_RATE_KEY] == "85000"
    assert "rollback" in session.events


def test_revision_009_and_models_keep_version_history_guards():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "009_usdt_rate_override.py"
    )
    spec = importlib.util.spec_from_file_location("migration_009", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    assert migration.revision == "009"
    assert migration.down_revision == "008"
    current_constraints = {
        constraint.name
        for constraint in rate_service.UsdtRateOverride.__table__.constraints
    }
    history_constraints = {
        constraint.name
        for constraint in rate_service.UsdtRateOverrideVersion.__table__.constraints
    }
    assert current_constraints >= {
        "ck_usdt_rate_override_singleton",
        "ck_usdt_rate_override_version",
        "ck_usdt_rate_override_state",
    }
    assert history_constraints >= {
        "uq_usdt_rate_override_version",
        "ck_usdt_rate_override_history_state",
    }


def test_durable_rate_cutover_defaults_off():
    assert Settings.model_fields["OPERATIONS_RATE_DB_ENABLED"].default is False
