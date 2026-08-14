from app.core.config import Settings
from app.core.redis import create_redis_client


def test_redis_pool_is_bounded_and_uses_bounded_retry():
    config = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:password@db/test",
        REDIS_URL="redis://127.0.0.1:6399/15",
        BOT_TOKEN="test-main-token",
        ADMIN_BOT_TOKEN="test-admin-token",
        TELEGRAM_BOT_MODE="disabled",
        WEB_APP_URL="https://example.test",
        REDIS_MAX_CONNECTIONS=17,
        REDIS_RETRY_ATTEMPTS=2,
        REDIS_RETRY_BACKOFF_MAX_SECONDS=0.25,
    )

    client = create_redis_client(config)
    pool = client.connection_pool

    assert pool.max_connections == 17
    retry = pool.connection_kwargs["retry"]
    assert retry._retries == 2
    assert retry._backoff._cap == 0.25
