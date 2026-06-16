import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException

from app.core.config import settings
from app.core.redis import redis_client

def _parse_init_data(init_data: str) -> Dict[str, str]:
    parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    if "hash" not in parsed_data:
        raise HTTPException(status_code=401, detail="Missing Telegram hash parameter.")
    return parsed_data

async def validate_telegram_data(
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
) -> Dict[str, Any]:
    if not init_data:
        if settings.ALLOW_INSECURE_DEV_AUTH:
            return {"user": json.dumps({"id": 0, "first_name": "Development", "username": "dev"})}
        raise HTTPException(status_code=401, detail="Telegram init data header is required.")

    cache_key = f"auth_session:{hashlib.md5(init_data.encode()).hexdigest()}"
    cached_session = await redis_client.get(cache_key)
    
    if cached_session:
        return json.loads(cached_session)

    parsed_data = _parse_init_data(init_data)
    received_hash = parsed_data.pop("hash")

    auth_date = parsed_data.get("auth_date")
    if auth_date:
        try:
            if time.time() - int(auth_date) > 86400:
                raise HTTPException(status_code=401, detail="Telegram init data has expired.")
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid Telegram auth date.")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed_data.items()))
    secret_key = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=403, detail="Invalid Telegram signature.")

    await redis_client.setex(cache_key, 86400, json.dumps(parsed_data))
    return parsed_data