import logging

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.schema_compatibility_service import check_schema_compatibility

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DATABASE_POOL_RECYCLE_SECONDS,
    connect_args={
        "server_settings": {
            "application_name": "keshepool",
            "statement_timeout": str(settings.DATABASE_STATEMENT_TIMEOUT_MS),
            "lock_timeout": str(settings.DATABASE_LOCK_TIMEOUT_MS),
            "idle_in_transaction_session_timeout": str(
                settings.DATABASE_IDLE_TRANSACTION_TIMEOUT_MS
            ),
        }
    },
)

AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with AsyncSessionLocal() as session:
        compatibility = await check_schema_compatibility(session)
    if not compatibility.ready:
        raise RuntimeError("Database schema is not compatible with this release.")
    logger.info(
        "Database schema and connection pool ready at revision %s.",
        ",".join(compatibility.current_revisions),
    )


def database_pool_snapshot() -> dict[str, int]:
    pool = engine.pool
    return {
        "size": int(pool.size()),
        "checkedOut": int(pool.checkedout()),
        "overflow": int(pool.overflow()),
        "maxOverflow": settings.DATABASE_MAX_OVERFLOW,
    }


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
