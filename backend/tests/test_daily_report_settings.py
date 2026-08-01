import asyncio
from unittest.mock import AsyncMock

from app.bot.services import daily_report_settings


def test_daily_report_defaults_to_disabled(monkeypatch):
    monkeypatch.setattr(daily_report_settings.redis_client, "get", AsyncMock(return_value=None))

    assert asyncio.run(daily_report_settings.is_daily_report_enabled()) is False


def test_daily_report_reads_enabled_value(monkeypatch):
    monkeypatch.setattr(daily_report_settings.redis_client, "get", AsyncMock(return_value="1"))

    assert asyncio.run(daily_report_settings.is_daily_report_enabled()) is True


def test_daily_report_toggle_is_atomic(monkeypatch):
    evaluate = AsyncMock(return_value="1")
    monkeypatch.setattr(daily_report_settings.redis_client, "eval", evaluate)

    assert asyncio.run(daily_report_settings.toggle_daily_report()) is True
    evaluate.assert_awaited_once()
    assert evaluate.await_args.args[1:] == (1, daily_report_settings.DAILY_REPORT_ENABLED_KEY)
