import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

from app.core.config import settings
from app.services.cache_service import namespaced_key, read_json, write_json

def _parse_init_data(init_data: str) -> Dict[str, str]:
    parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    if "hash" not in parsed_data:
        raise HTTPException(status_code=401, detail="Missing Telegram hash parameter.")
    return parsed_data

async def validate_telegram_data(
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
) -> Dict[str, Any]:
    if not init_data:
        if settings.ALLOW_INSECURE_DEV_AUTH and settings.ENVIRONMENT.lower() != "production":
            return {"user": json.dumps({"id": 0, "first_name": "Development", "username": "dev"})}
        raise HTTPException(status_code=401, detail="Telegram init data header is required.")

    parsed_data = _parse_init_data(init_data)
    received_hash = parsed_data.pop("hash")
    _, remaining_lifetime = validate_auth_date(parsed_data.get("auth_date"))

    cache_key = namespaced_key(
        f"auth-session:{hashlib.sha256(init_data.encode()).hexdigest()}"
    )
    cached_session = await read_json(cache_key)
    if cached_session.hit and isinstance(cached_session.value, dict):
        return cached_session.value

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed_data.items()))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=403, detail="Invalid Telegram signature.")

    await write_json(cache_key, parsed_data, remaining_lifetime)
    return parsed_data


def validate_auth_date(auth_date: str | None, *, now: int | None = None) -> tuple[int, int]:
    if auth_date is None or auth_date == "":
        raise HTTPException(status_code=401, detail="Telegram auth date is required.")
    try:
        auth_timestamp = int(auth_date)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid Telegram auth date.") from exc

    current_timestamp = int(time.time()) if now is None else int(now)
    if auth_timestamp > current_timestamp + settings.TELEGRAM_AUTH_FUTURE_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="Telegram auth date is in the future.")

    age_seconds = current_timestamp - auth_timestamp
    if age_seconds > settings.TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Telegram init data has expired.")

    remaining_seconds = min(
        settings.TELEGRAM_AUTH_MAX_AGE_SECONDS,
        auth_timestamp + settings.TELEGRAM_AUTH_MAX_AGE_SECONDS - current_timestamp,
    )
    return auth_timestamp, max(1, remaining_seconds)
