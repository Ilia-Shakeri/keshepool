from app.core.redis import redis_client
from app.services.cache_service import namespaced_key


DAILY_REPORT_ENABLED_KEY = namespaced_key("admin:daily-report-enabled")

_TOGGLE_DAILY_REPORT_SCRIPT = """
local enabled = redis.call('get', KEYS[1]) == '1'
local next_value = enabled and '0' or '1'
redis.call('set', KEYS[1], next_value)
return next_value
"""


async def is_daily_report_enabled() -> bool:
    return await redis_client.get(DAILY_REPORT_ENABLED_KEY) == "1"


async def toggle_daily_report() -> bool:
    value = await redis_client.eval(
        _TOGGLE_DAILY_REPORT_SCRIPT,
        1,
        DAILY_REPORT_ENABLED_KEY,
    )
    return str(value) == "1"
