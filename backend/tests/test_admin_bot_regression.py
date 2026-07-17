import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from fastapi import HTTPException
from starlette.requests import Request

from app import main
from app.bot.handlers import admin_panel
from app.bot.locales.translations import get_text


def make_request(payload) -> Request:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/webhook/admin",
            "headers": [],
            "state": {"request_id": "request-1234"},
        },
        receive,
    )


def test_allowlisted_admin_start_clears_state_and_sends_both_menus(monkeypatch):
    state = SimpleNamespace(clear=AsyncMock())
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=123456),
        answer=AsyncMock(),
    )
    monkeypatch.setattr(admin_panel, "get_admin_lang", AsyncMock(return_value="fa"))

    asyncio.run(admin_panel.cmd_start(message, state))

    state.clear.assert_awaited_once()
    assert message.answer.await_count == 2
    first = message.answer.await_args_list[0].kwargs
    second = message.answer.await_args_list[1].kwargs
    assert first["text"] == get_text("fa", "main_menu")
    assert isinstance(first["reply_markup"], InlineKeyboardMarkup)
    assert second["text"] == get_text("fa", "persistent_hint")
    assert isinstance(second["reply_markup"], ReplyKeyboardMarkup)
    assert second["reply_markup"].is_persistent is True


def test_webhook_status_fields_do_not_expose_url_or_secret():
    expected_url = "https://example.test/webhook/admin"
    fields = main._safe_webhook_info(
        "admin",
        expected_url,
        SimpleNamespace(
            url=expected_url,
            pending_update_count=2,
            last_error_date=None,
            last_error_message=None,
        ),
    )
    assert fields["configured"] is True
    assert fields["url_matches_expected"] is True
    assert fields["pending_update_count"] == 2
    assert expected_url not in json.dumps(fields)
    assert "secret" not in fields


@pytest.mark.parametrize("bot_type, dispatcher_name", [("admin", "admin_dp"), ("main", "dp")])
def test_valid_webhook_update_uses_matching_dispatcher(monkeypatch, bot_type, dispatcher_name):
    dispatcher = AsyncMock()
    monkeypatch.setattr(main, dispatcher_name, dispatcher)
    response = asyncio.run(
        main.bot_webhook(
            bot_type,
            make_request({"update_id": 1001}),
            main.settings.WEBHOOK_SECRET,
        )
    )
    assert response == {"status": "ok"}
    dispatcher.feed_update.assert_awaited_once()


@pytest.mark.parametrize("secret", [None, "wrong-secret"])
def test_missing_or_incorrect_webhook_secret_returns_401(secret):
    with pytest.raises(HTTPException) as raised:
        asyncio.run(main.bot_webhook("admin", make_request({"update_id": 1}), secret))
    assert raised.value.status_code == 401


def test_malformed_webhook_payload_is_safely_ignored():
    response = asyncio.run(
        main.bot_webhook("admin", make_request(b"not-json"), main.settings.WEBHOOK_SECRET)
    )
    assert response == {"status": "ignored"}


def test_webhook_handler_failure_returns_503(monkeypatch):
    dispatcher = AsyncMock()
    dispatcher.feed_update.side_effect = RuntimeError("handler failed")
    monkeypatch.setattr(main, "admin_dp", dispatcher)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            main.bot_webhook(
                "admin",
                make_request({"update_id": 1002}),
                main.settings.WEBHOOK_SECRET,
            )
        )
    assert raised.value.status_code == 503
