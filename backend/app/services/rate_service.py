import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import httpx
from redis.exceptions import RedisError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.models import UsdtRateOverride, UsdtRateOverrideVersion
from app.services.admin_audit_service import add_admin_audit
from app.services.cache_service import (
    delete_keys,
    namespaced_key,
    read_json,
    write_json,
)

logger = logging.getLogger(__name__)

# This key stays compatible with older application instances during a rolling update.
USDT_RATE_KEY = namespaced_key("config:usdt-to-irr-rate")
USDT_RATE_DB_CACHE_KEY = namespaced_key("config:usdt-to-irr-rate", version="v2")
USDT_LIVE_RATE_KEY = namespaced_key("cache:usdt-live-rate")
LIVE_RATE_TTL = 90
DB_RATE_CACHE_TTL = 300
RATE_OVERRIDE_SINGLETON_ID = 1
MAX_USDT_RATE = Decimal("9999999999999999")

NOBITEX_URL = "https://api.nobitex.ir/v2/orderbook/USDTIRT"
WALLEX_URL = "https://api.wallex.ir/v1/markets"


@dataclass(frozen=True)
class RateOverrideState:
    exists: bool
    is_active: bool
    version: int | None = None
    rate: Decimal | None = None

    @classmethod
    def missing(cls) -> "RateOverrideState":
        return cls(exists=False, is_active=False)


def _parse_positive_rate(raw_value: object) -> Decimal | None:
    if isinstance(raw_value, bytes):
        try:
            raw_value = raw_value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    try:
        value = Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not value.is_finite() or value <= 0 or value > MAX_USDT_RATE:
        return None
    return value


def _rate_for_write(rate: int) -> Decimal:
    if isinstance(rate, bool) or not isinstance(rate, int):
        raise ValueError("USDT rate must be a positive integer.")
    value = _parse_positive_rate(rate)
    if value is None:
        raise ValueError("USDT rate is outside the supported range.")
    return value


def _audit_actor(actor_telegram_id: int | str | None) -> str | None:
    if actor_telegram_id is None:
        return None
    actor = str(actor_telegram_id).strip()
    if not actor.isdigit() or len(actor) > 20:
        raise ValueError("Invalid rate-change actor.")
    return actor


def _audit_source(change_source: str) -> str:
    source = change_source.strip()
    if not re.fullmatch(r"[a-z0-9._-]{1,32}", source):
        raise ValueError("Invalid rate-change source.")
    return source


def _state_from_row(row: UsdtRateOverride | None) -> RateOverrideState:
    if row is None:
        return RateOverrideState.missing()
    version = int(row.version)
    if version <= 0:
        raise ValueError("Invalid durable rate version.")
    if not row.is_active:
        if row.rate is not None:
            raise ValueError("Invalid cleared durable rate state.")
        return RateOverrideState(exists=True, is_active=False, version=version)
    rate = _parse_positive_rate(row.rate)
    if rate is None:
        raise ValueError("Invalid active durable rate state.")
    return RateOverrideState(exists=True, is_active=True, version=version, rate=rate)


async def _load_db_override() -> RateOverrideState:
    async with AsyncSessionLocal() as session:
        row = await session.get(UsdtRateOverride, RATE_OVERRIDE_SINGLETON_ID)
        return _state_from_row(row)


async def apply_usdt_rate_override_in_session(
    session: AsyncSession,
    *,
    rate: int | None,
    actor_telegram_id: int | str | None = None,
    change_source: str = "admin_bot",
) -> RateOverrideState:
    """Stage a rate change and its audit rows without committing the session."""
    if not settings.OPERATIONS_RATE_DB_ENABLED:
        raise RuntimeError("Durable rate storage is disabled.")
    normalized_rate = None if rate is None else _rate_for_write(rate)
    is_active = normalized_rate is not None
    actor = _audit_actor(actor_telegram_id)
    source = _audit_source(change_source)
    now = datetime.now(timezone.utc)
    statement = insert(UsdtRateOverride).values(
        id=RATE_OVERRIDE_SINGLETON_ID,
        rate=normalized_rate,
        is_active=is_active,
        version=1,
        changed_by_telegram_id=actor,
        change_source=source,
        updated_at=now,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[UsdtRateOverride.id],
        set_={
            "rate": statement.excluded.rate,
            "is_active": statement.excluded.is_active,
            "version": UsdtRateOverride.version + 1,
            "changed_by_telegram_id": statement.excluded.changed_by_telegram_id,
            "change_source": statement.excluded.change_source,
            "updated_at": now,
        },
    ).returning(UsdtRateOverride.version)
    version = await session.scalar(statement)
    if version is None:
        raise RuntimeError("Durable rate update returned no version.")
    session.add(
        UsdtRateOverrideVersion(
            version=int(version),
            rate=normalized_rate,
            is_active=is_active,
            changed_by_telegram_id=actor,
            change_source=source,
            created_at=now,
        )
    )
    if actor is not None:
        details: dict[str, object] = {
            "version": int(version),
            "source": source,
        }
        if normalized_rate is not None:
            details["rate"] = int(normalized_rate)
        await add_admin_audit(
            session,
            actor_telegram_id=actor,
            action=(
                "exchange_rate.manual_override"
                if is_active
                else "exchange_rate.return_to_live"
            ),
            target_type="exchange_rate",
            target_id="USDT_IRR",
            details=details,
        )
    else:
        await session.flush()
    return RateOverrideState(
        exists=True,
        is_active=is_active,
        version=int(version),
        rate=normalized_rate,
    )


async def _commit_db_override(
    *,
    rate: int | None,
    actor_telegram_id: int | str | None,
    change_source: str,
) -> RateOverrideState:
    async with AsyncSessionLocal() as session:
        try:
            state = await apply_usdt_rate_override_in_session(
                session,
                rate=rate,
                actor_telegram_id=actor_telegram_id,
                change_source=change_source,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    return state


async def _import_legacy_override(rate: Decimal) -> RateOverrideState:
    now = datetime.now(timezone.utc)
    source = "legacy_redis_import"
    async with AsyncSessionLocal() as session:
        statement = (
            insert(UsdtRateOverride)
            .values(
                id=RATE_OVERRIDE_SINGLETON_ID,
                rate=rate,
                is_active=True,
                version=1,
                changed_by_telegram_id=None,
                change_source=source,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=[UsdtRateOverride.id])
            .returning(UsdtRateOverride.version)
        )
        try:
            version = await session.scalar(statement)
            if version is not None:
                session.add(
                    UsdtRateOverrideVersion(
                        version=int(version),
                        rate=rate,
                        is_active=True,
                        changed_by_telegram_id=None,
                        change_source=source,
                        created_at=now,
                    )
                )
                await session.commit()
                return RateOverrideState(
                    exists=True,
                    is_active=True,
                    version=int(version),
                    rate=rate,
                )
            row = await session.get(UsdtRateOverride, RATE_OVERRIDE_SINGLETON_ID)
            return _state_from_row(row)
        except Exception:
            await session.rollback()
            raise


async def cache_usdt_rate_override(state: RateOverrideState) -> None:
    """Refresh Redis after the caller has committed the durable transaction."""
    if not state.exists or state.version is None:
        await delete_keys(USDT_RATE_DB_CACHE_KEY)
        return
    await write_json(
        USDT_RATE_DB_CACHE_KEY,
        {
            "version": state.version,
            "isActive": state.is_active,
            "rate": str(state.rate) if state.rate is not None else None,
        },
        DB_RATE_CACHE_TTL,
    )
    if not state.is_active:
        await delete_keys(USDT_RATE_KEY)
        return
    try:
        await redis_client.set(USDT_RATE_KEY, str(state.rate))
    except RedisError as exc:
        logger.warning("Legacy rate cache write failed: %s", type(exc).__name__)


async def _read_db_override_cache() -> RateOverrideState | None:
    cached = await read_json(USDT_RATE_DB_CACHE_KEY)
    if not cached.hit:
        return None
    if not isinstance(cached.value, dict):
        await delete_keys(USDT_RATE_DB_CACHE_KEY)
        return None
    value = cached.value
    version = value.get("version")
    is_active = value.get("isActive")
    if isinstance(version, bool) or not isinstance(version, int) or version <= 0:
        await delete_keys(USDT_RATE_DB_CACHE_KEY)
        return None
    if not isinstance(is_active, bool):
        await delete_keys(USDT_RATE_DB_CACHE_KEY)
        return None
    if not is_active:
        if value.get("rate") is not None:
            await delete_keys(USDT_RATE_DB_CACHE_KEY)
            return None
        return RateOverrideState(exists=True, is_active=False, version=version)
    rate = _parse_positive_rate(value.get("rate"))
    if rate is None:
        await delete_keys(USDT_RATE_DB_CACHE_KEY)
        return None
    return RateOverrideState(exists=True, is_active=True, version=version, rate=rate)


async def _read_legacy_override() -> Decimal | None:
    try:
        manual = await redis_client.get(USDT_RATE_KEY)
    except RedisError as exc:
        logger.warning("Rate cache unavailable: %s", type(exc).__name__)
        return None
    if manual is None:
        return None
    rate = _parse_positive_rate(manual)
    if rate is not None:
        return rate
    logger.warning("Invalid manual rate cache value removed")
    await delete_keys(USDT_RATE_KEY)
    return None


async def _durable_override() -> RateOverrideState:
    try:
        state = await _load_db_override()
    except SQLAlchemyError as exc:
        logger.error("Durable rate read failed: %s", type(exc).__name__)
        cached = await _read_db_override_cache()
        return cached or RateOverrideState.missing()
    except ValueError as exc:
        logger.error("Durable rate state rejected: %s", exc)
        await delete_keys(USDT_RATE_DB_CACHE_KEY, USDT_RATE_KEY)
        return RateOverrideState.missing()

    if not state.exists:
        legacy_rate = await _read_legacy_override()
        if legacy_rate is not None:
            try:
                state = await _import_legacy_override(legacy_rate)
            except SQLAlchemyError as exc:
                logger.error("Legacy rate import failed: %s", type(exc).__name__)
                cached = await _read_db_override_cache()
                return cached or RateOverrideState.missing()
            except ValueError as exc:
                logger.error("Imported durable rate state rejected: %s", exc)
                await delete_keys(USDT_RATE_DB_CACHE_KEY, USDT_RATE_KEY)
                return RateOverrideState.missing()
        else:
            await delete_keys(USDT_RATE_DB_CACHE_KEY)
            return state

    await cache_usdt_rate_override(state)
    return state


async def _fetch_live_rate() -> Decimal | None:
    """Fetch the current USDT rate from a live market source."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(NOBITEX_URL)
            res.raise_for_status()
            data = res.json()
        price_rial = data.get("lastTradePrice")
        if not price_rial:
            asks = data.get("asks") or []
            price_rial = asks[0][0] if asks else None
        if price_rial:
            toman = Decimal(str(price_rial)) / Decimal("10")
            if toman > 0:
                return toman.quantize(Decimal("1"))
    except (httpx.HTTPError, ValueError, TypeError, InvalidOperation, KeyError, IndexError) as exc:
        logger.warning("Nobitex rate fetch failed: %s", exc)

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.get(WALLEX_URL)
            res.raise_for_status()
            data = res.json()
        symbols = data.get("result", {}).get("symbols", {})
        stats = symbols.get("USDTTMN", {}).get("stats", {})
        price = stats.get("lastPrice") or stats.get("bidPrice")
        if price:
            toman = Decimal(str(price))
            if toman > 0:
                return toman.quantize(Decimal("1"))
    except (httpx.HTTPError, ValueError, TypeError, InvalidOperation, KeyError) as exc:
        logger.warning("Wallex rate fetch failed: %s", exc)

    return None


async def _read_live_cache() -> Decimal | None:
    try:
        cached = await redis_client.get(USDT_LIVE_RATE_KEY)
    except RedisError as exc:
        logger.warning("Live rate cache unavailable: %s", type(exc).__name__)
        return None
    if cached is None:
        return None
    rate = _parse_positive_rate(cached)
    if rate is not None:
        return rate
    logger.warning("Invalid live rate cache value removed")
    await delete_keys(USDT_LIVE_RATE_KEY)
    return None


async def get_usdt_rate() -> Decimal:
    """Return the durable override, live market rate, or reviewed static fallback."""
    if settings.OPERATIONS_RATE_DB_ENABLED:
        state = await _durable_override()
        if state.is_active and state.rate is not None:
            return state.rate
    else:
        manual = await _read_legacy_override()
        if manual is not None:
            return manual

    cached = await _read_live_cache()
    if cached is not None:
        return cached

    live = await _fetch_live_rate()
    if live and live > 0:
        try:
            await redis_client.setex(USDT_LIVE_RATE_KEY, LIVE_RATE_TTL, str(live))
        except RedisError as exc:
            logger.warning("Live rate cache write failed: %s", type(exc).__name__)
        return live

    logger.warning("All live rate sources failed; falling back to static rate.")
    return Decimal(str(settings.USDT_TO_IRR_RATE))


async def set_usdt_rate(
    rate: int,
    *,
    actor_telegram_id: int | str | None = None,
    change_source: str = "admin_bot",
) -> None:
    """Persist a manual override, using PostgreSQL when durable mode is enabled."""
    normalized_rate = _rate_for_write(rate)
    if not settings.OPERATIONS_RATE_DB_ENABLED:
        await redis_client.set(USDT_RATE_KEY, str(rate))
        return
    state = await _commit_db_override(
        rate=int(normalized_rate),
        actor_telegram_id=actor_telegram_id,
        change_source=change_source,
    )
    await cache_usdt_rate_override(state)


async def clear_usdt_rate_override(
    *,
    actor_telegram_id: int | str | None = None,
    change_source: str = "admin_bot",
) -> None:
    """Record a clear event, or use the old Redis path while the flag is off."""
    if not settings.OPERATIONS_RATE_DB_ENABLED:
        await redis_client.delete(USDT_RATE_KEY)
        return
    state = await _commit_db_override(
        rate=None,
        actor_telegram_id=actor_telegram_id,
        change_source=change_source,
    )
    await cache_usdt_rate_override(state)
