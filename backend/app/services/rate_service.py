from decimal import Decimal

from app.core.config import settings
from app.core.redis import redis_client

USDT_RATE_KEY = "config:usdt_to_irr_rate"


async def get_usdt_rate() -> Decimal:
    """Return the active USDT→Toman rate.

    Redis value takes precedence over the .env default so admins
    can update the rate at runtime without a redeploy.
    """
    stored = await redis_client.get(USDT_RATE_KEY)
    if stored:
        try:
            return Decimal(stored)
        except Exception:
            pass
    return Decimal(str(settings.USDT_TO_IRR_RATE))


async def set_usdt_rate(rate: int) -> None:
    """Persist a new USDT→Toman rate to Redis."""
    await redis_client.set(USDT_RATE_KEY, str(rate))
