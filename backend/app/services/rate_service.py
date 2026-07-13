import logging
from decimal import Decimal, InvalidOperation

import httpx
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis import redis_client
from app.services.cache_service import delete_keys, namespaced_key

logger = logging.getLogger(__name__)

# Admin-set manual override (no expiry) — wins over live market data when present.
USDT_RATE_KEY = namespaced_key("config:usdt-to-irr-rate")
# Short-lived cache of the last successful live fetch.
USDT_LIVE_RATE_KEY = namespaced_key("cache:usdt-live-rate")
LIVE_RATE_TTL = 90  # seconds

# Iranian exchanges quote USDT against local currency/Rial. Nobitex is primary, Wallex is fallback.
NOBITEX_URL = "https://api.nobitex.ir/v2/orderbook/USDTIRT"
WALLEX_URL = "https://api.wallex.ir/v1/markets"


async def _fetch_live_rate() -> Decimal | None:
    """Fetch the current USDT rate from a live market source.

    Returns local currency per 1 USDT, or None if every provider is unreachable.
    """
    # Nobitex quotes in Rial, so divide by 10 to reach the wallet unit.
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

    # Wallex quotes USDT/TMN directly in the wallet unit.
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


async def get_usdt_rate() -> Decimal:
    """Return the active USDT rate in the wallet unit.

    Resolution order:
      1. Admin manual override in Redis — full operator control.
      2. Cached live rate (short TTL) — avoids hammering the upstream API.
      3. Fresh live fetch — cached on success.
      4. Static .env default — last-resort fallback if all sources fail.
    """
    try:
        manual = await redis_client.get(USDT_RATE_KEY)
        cached = await redis_client.get(USDT_LIVE_RATE_KEY)
    except RedisError as exc:
        logger.warning("Rate cache unavailable: %s", type(exc).__name__)
        manual = None
        cached = None

    if manual:
        try:
            value = Decimal(manual)
            if value > 0:
                return value
            raise InvalidOperation
        except (InvalidOperation, TypeError):
            logger.warning("Invalid manual rate cache value removed")
            await delete_keys(USDT_RATE_KEY)

    if cached:
        try:
            value = Decimal(cached)
            if value > 0:
                return value
            raise InvalidOperation
        except (InvalidOperation, TypeError):
            logger.warning("Invalid live rate cache value removed")
            await delete_keys(USDT_LIVE_RATE_KEY)

    live = await _fetch_live_rate()
    if live and live > 0:
        try:
            await redis_client.setex(USDT_LIVE_RATE_KEY, LIVE_RATE_TTL, str(live))
        except RedisError as exc:
            logger.warning("Live rate cache write failed: %s", type(exc).__name__)
        return live

    logger.warning("All live rate sources failed; falling back to static rate.")
    return Decimal(str(settings.USDT_TO_IRR_RATE))


async def set_usdt_rate(rate: int) -> None:
    """Persist an admin manual override for the USDT wallet-unit rate."""
    await redis_client.set(USDT_RATE_KEY, str(rate))


async def clear_usdt_rate_override() -> None:
    """Return rate selection to the live source order."""
    await redis_client.delete(USDT_RATE_KEY)
