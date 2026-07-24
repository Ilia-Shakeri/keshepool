import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import cashout
from app.api.cashout import CashoutRequestCreate
from app.services.cache_service import RateLimitDecision


def test_other_cashout_platform_requires_custom_source_even_when_field_is_omitted():
    with pytest.raises(ValidationError, match="custom_source"):
        CashoutRequestCreate(
            source_platform="other",
            details_text="Valid request details",
        )


def test_cashout_details_reject_whitespace_and_normalize_valid_text():
    with pytest.raises(ValidationError, match="non-space"):
        CashoutRequestCreate(
            source_platform="wise",
            details_text="          ",
        )

    payload = CashoutRequestCreate(
        source_platform="other",
        custom_source="  Local platform  ",
        details_text="  Valid request details  ",
    )
    assert payload.custom_source == "Local platform"
    assert payload.details_text == "Valid request details"


def test_cashout_rate_limit_fails_closed_when_redis_is_offline(monkeypatch):
    monkeypatch.setattr(
        cashout,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=None,
                backend_available=False,
            )
        ),
    )
    payload = CashoutRequestCreate(
        source_platform="wise",
        details_text="Valid request details",
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            cashout.create_cashout_request(
                payload,
                SimpleNamespace(id=1, telegram_id="42"),
                AsyncMock(),
            )
        )
    assert raised.value.status_code == 503
