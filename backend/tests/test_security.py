import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse

import pytest
from fastapi import HTTPException

from app.core import security
from app.services.cache_service import CacheRead


def _signed_init_data(auth_date: int) -> str:
    payload = {
        "auth_date": str(auth_date),
        "query_id": "test-query",
        "user": json.dumps({"id": 42, "first_name": "Test"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret = hmac.new(
        b"WebAppData",
        security.settings.BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()
    payload["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(payload)


def test_auth_date_is_required_and_bounded():
    now = 1_700_000_000
    with pytest.raises(HTTPException, match="required"):
        security.validate_auth_date(None, now=now)
    with pytest.raises(HTTPException, match="future"):
        security.validate_auth_date(
            str(now + security.settings.TELEGRAM_AUTH_FUTURE_SKEW_SECONDS + 1),
            now=now,
        )
    with pytest.raises(HTTPException, match="expired"):
        security.validate_auth_date(
            str(now - security.settings.TELEGRAM_AUTH_MAX_AGE_SECONDS - 1),
            now=now,
        )


def test_auth_cache_ttl_uses_only_remaining_init_data_lifetime(monkeypatch):
    now = int(time.time())
    init_data = _signed_init_data(now - 120)
    writes = []

    async def cache_miss(key):
        return CacheRead(available=True, hit=False)

    async def capture_write(key, value, ttl_seconds):
        writes.append((key, value, ttl_seconds))
        return True

    monkeypatch.setattr(security, "read_json", cache_miss)
    monkeypatch.setattr(security, "write_json", capture_write)
    result = asyncio.run(security.validate_telegram_data(init_data))

    assert json.loads(result["user"])["id"] == 42
    assert len(writes) == 1
    ttl = writes[0][2]
    assert 1 <= ttl <= security.settings.TELEGRAM_AUTH_MAX_AGE_SECONDS - 119


def test_expired_init_data_is_rejected_before_cache_lookup(monkeypatch):
    now = int(time.time())
    init_data = _signed_init_data(
        now - security.settings.TELEGRAM_AUTH_MAX_AGE_SECONDS - 5
    )
    cache_called = False

    async def poisoned_cache(key):
        nonlocal cache_called
        cache_called = True
        return CacheRead(available=True, hit=True, value={"user": "{}"})

    monkeypatch.setattr(security, "read_json", poisoned_cache)
    with pytest.raises(HTTPException, match="expired"):
        asyncio.run(security.validate_telegram_data(init_data))
    assert cache_called is False
