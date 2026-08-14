import redis.asyncio as redis
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import settings


def create_redis_client(config=settings):
    return redis.from_url(
        config.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=config.REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=config.REDIS_SOCKET_TIMEOUT_SECONDS,
        max_connections=config.REDIS_MAX_CONNECTIONS,
        health_check_interval=30,
        retry=Retry(
            ExponentialBackoff(
                cap=config.REDIS_RETRY_BACKOFF_MAX_SECONDS,
                base=0.05,
            ),
            config.REDIS_RETRY_ATTEMPTS,
        ),
        retry_on_timeout=True,
    )


redis_client = create_redis_client()
