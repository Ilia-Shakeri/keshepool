import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.core.database import database_pool_snapshot, engine


def _settings_values(**overrides):
    values = {
        "_env_file": None,
        "DATABASE_URL": "postgresql+asyncpg://user:password@db/test",
        "BOT_TOKEN": "test-main-token",
        "ADMIN_BOT_TOKEN": "test-admin-token",
        "TELEGRAM_BOT_MODE": "disabled",
        "WEB_APP_URL": "https://example.test",
    }
    values.update(overrides)
    return values


def test_database_timeouts_require_lock_wait_below_statement_budget():
    with pytest.raises(ValidationError, match="DATABASE_LOCK_TIMEOUT_MS"):
        Settings(
            **_settings_values(
                DATABASE_LOCK_TIMEOUT_MS=5000,
                DATABASE_STATEMENT_TIMEOUT_MS=5000,
            )
        )


def test_runtime_engine_has_bounded_pool_and_server_timeouts():
    pool = engine.pool
    snapshot = database_pool_snapshot()

    assert snapshot["size"] == settings.DATABASE_POOL_SIZE
    assert snapshot["maxOverflow"] == settings.DATABASE_MAX_OVERFLOW
    assert snapshot["checkedOut"] >= 0
    assert pool._timeout == settings.DATABASE_POOL_TIMEOUT_SECONDS
    assert pool._recycle == settings.DATABASE_POOL_RECYCLE_SECONDS
