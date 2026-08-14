import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import ForceReply, InlineKeyboardMarkup, ReplyKeyboardMarkup
from fastapi import HTTPException
from starlette.requests import Request

from app import main
from app.bot.handlers import admin_panel, products_admin, transactions_admin
from app.bot.locales.translations import get_text


def make_request(payload, content_type="application/json") -> Request:
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
            "headers": [(b"content-type", content_type.encode("ascii"))],
            "state": {"request_id": "request-1234"},
        },
        receive,
    )


def test_wallet_approval_snapshot_is_canonical_and_complete():
    transaction = SimpleNamespace(
        id=7,
        amount="12.50",
        currency="USDT",
    )
    snapshot = transactions_admin._wallet_approval_snapshot(
        transaction,
        rate=transactions_admin.Decimal("85000"),
        credit=transactions_admin.Decimal("1062500.00"),
    )
    assert json.loads(snapshot) == {
        "amount": "12.50",
        "credit": "1062500.00",
        "currency": "USDT",
        "rate": "85000",
        "transaction_id": 7,
    }
    assert snapshot == transactions_admin._wallet_approval_snapshot(
        transaction,
        rate=transactions_admin.Decimal("85000"),
        credit=transactions_admin.Decimal("1062500.00"),
    )


def test_mass_catalog_approval_snapshot_is_sorted_and_stable():
    assert products_admin._catalog_removal_snapshot(["z", "a", "m"]) == b'["a","m","z"]'


def test_transaction_report_approval_snapshot_is_canonical():
    start = transactions_admin.datetime(2026, 1, 1, tzinfo=transactions_admin.timezone.utc)
    end = transactions_admin.datetime(2026, 1, 2, tzinfo=transactions_admin.timezone.utc)
    snapshot = transactions_admin._transaction_report_snapshot(start, end, "fa")
    assert json.loads(snapshot) == {
        "end": "2026-01-02T00:00:00+00:00",
        "lang": "fa",
        "start": "2026-01-01T00:00:00+00:00",
    }


def test_rate_approval_snapshot_binds_old_new_and_clear_state():
    assert json.loads(admin_panel._rate_approval_snapshot(90_000, 120_000, 4)) == {
        "expected_version": 4,
        "old": 90_000,
        "new": 120_000,
    }
    assert json.loads(admin_panel._rate_approval_snapshot(90_000, None, 0)) == {
        "expected_version": 0,
        "old": 90_000,
        "new": None,
    }


def test_rate_dual_approval_threshold_is_conservative_and_bounded():
    assert admin_panel._rate_change_needs_dual_approval(100_000, 110_000, 10)
    assert admin_panel._rate_change_needs_dual_approval(100_000, 90_000, 10)
    assert not admin_panel._rate_change_needs_dual_approval(100_000, 109_999, 10)
    with pytest.raises(ValueError):
        admin_panel._rate_change_needs_dual_approval(0, 100_000, 10)


def test_admin_message_bounds_cover_direct_and_bulk_delivery():
    assert admin_panel._bounded_admin_message("Title\nBody") == ("Title", "Body")
    assert admin_panel._bounded_admin_message("Title") == ("Title", "Title")
    assert admin_panel._bounded_admin_message(None) is None
    assert admin_panel._bounded_admin_message("x" * 101) is None
    assert admin_panel._bounded_admin_message("ok\n" + "x" * 3501) is None
    assert admin_panel._bounded_admin_message("ok\nunsafe\x00text") is None


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


def test_group_start_uses_only_reliable_inline_menu(monkeypatch):
    state = SimpleNamespace(clear=AsyncMock())
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=123456),
        chat=SimpleNamespace(type="supergroup"),
        answer=AsyncMock(),
    )
    monkeypatch.setattr(admin_panel, "get_admin_lang", AsyncMock(return_value="fa"))
    asyncio.run(admin_panel.cmd_start(message, state))
    assert message.answer.await_count == 1
    assert isinstance(message.answer.await_args.kwargs["reply_markup"], InlineKeyboardMarkup)


def test_guided_text_step_uses_selective_force_reply():
    target = SimpleNamespace(answer=AsyncMock())
    state = SimpleNamespace(set_state=AsyncMock())
    asyncio.run(products_admin._prompt_guided_title(target, "fa", state))
    force_reply = target.answer.await_args.kwargs["reply_markup"]
    assert isinstance(force_reply, ForceReply)
    assert force_reply.selective is True


def test_dispatchers_use_durable_redis_fsm_storage():
    assert isinstance(main.dp.storage, RedisStorage)
    assert isinstance(main.admin_dp.storage, RedisStorage)


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


@pytest.mark.parametrize("bot_type", ["admin", "main"])
def test_valid_webhook_update_is_queued(monkeypatch, bot_type):
    enqueue = AsyncMock(return_value=True)
    monkeypatch.setattr(main, "enqueue_update", enqueue)
    response = asyncio.run(
        main.bot_webhook(
            bot_type,
            make_request({"update_id": 1001}),
            (
                main.settings.admin_telegram_webhook_secret
                if bot_type == "admin"
                else main.settings.main_telegram_webhook_secret
            ),
        )
    )
    assert response == {"status": "queued"}
    assert enqueue.await_args.kwargs["bot_type"] == bot_type
    assert enqueue.await_args.kwargs["update_id"] == 1001


@pytest.mark.parametrize("secret", [None, "wrong-secret"])
def test_missing_or_incorrect_webhook_secret_returns_401(secret):
    with pytest.raises(HTTPException) as raised:
        asyncio.run(main.bot_webhook("admin", make_request({"update_id": 1}), secret))
    assert raised.value.status_code == 401


def test_unconfigured_webhook_secret_fails_closed(monkeypatch):
    monkeypatch.setattr(main.settings, "ADMIN_TELEGRAM_WEBHOOK_SECRET", "")
    monkeypatch.setattr(main.settings, "WEBHOOK_SECRET", "")
    with pytest.raises(HTTPException) as raised:
        asyncio.run(main.bot_webhook("admin", make_request({"update_id": 1}), None))
    assert raised.value.status_code == 503


def test_webhook_requires_json_content_type_and_object_body():
    with pytest.raises(HTTPException) as wrong_type:
        asyncio.run(
            main.bot_webhook(
                "admin",
                make_request({"update_id": 1}, "text/plain"),
                main.settings.admin_telegram_webhook_secret,
            )
        )
    assert wrong_type.value.status_code == 415

    with pytest.raises(HTTPException) as wrong_shape:
        asyncio.run(
            main.bot_webhook(
                "admin",
                make_request([]),
                main.settings.admin_telegram_webhook_secret,
            )
        )
    assert wrong_shape.value.status_code == 400


def test_malformed_webhook_payload_is_safely_ignored():
    response = asyncio.run(
        main.bot_webhook(
            "admin",
            make_request(b"not-json"),
            main.settings.admin_telegram_webhook_secret,
        )
    )
    assert response == {"status": "ignored"}


def test_malformed_utf8_webhook_payload_is_safely_ignored():
    response = asyncio.run(
        main.bot_webhook(
            "admin",
            make_request(b'{"update_id":1,"text":"\xff"}'),
            main.settings.admin_telegram_webhook_secret,
        )
    )
    assert response == {"status": "ignored"}


def test_deep_webhook_json_is_rejected(monkeypatch):
    monkeypatch.setattr(main.settings, "TELEGRAM_WEBHOOK_MAX_JSON_DEPTH", 4)
    payload = {"update_id": 1, "a": {"b": {"c": {"d": "too deep"}}}}
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            main.bot_webhook(
                "admin",
                make_request(payload),
                main.settings.admin_telegram_webhook_secret,
            )
        )
    assert raised.value.status_code == 400


def test_oversized_webhook_payload_returns_413(monkeypatch):
    monkeypatch.setattr(main.settings, "TELEGRAM_WEBHOOK_MAX_BYTES", 32)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            main.bot_webhook(
                "admin",
                make_request(b"x" * 33),
                main.settings.admin_telegram_webhook_secret,
            )
        )
    assert raised.value.status_code == 413


def test_webhook_inbox_failure_returns_503(monkeypatch):
    monkeypatch.setattr(
        main,
        "enqueue_update",
        AsyncMock(side_effect=RuntimeError("database unavailable")),
    )
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            main.bot_webhook(
                "admin",
                make_request({"update_id": 1002}),
                main.settings.admin_telegram_webhook_secret,
            )
        )
    assert raised.value.status_code == 503


def test_duplicate_webhook_update_is_acknowledged(monkeypatch):
    monkeypatch.setattr(main, "enqueue_update", AsyncMock(return_value=False))
    response = asyncio.run(
        main.bot_webhook(
            "admin",
            make_request({"update_id": 1004}),
            main.settings.admin_telegram_webhook_secret,
        )
    )
    assert response == {"status": "duplicate"}


def test_main_webhook_secret_cannot_reach_admin_dispatcher():
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            main.bot_webhook(
                "admin",
                make_request({"update_id": 1003}),
                main.settings.main_telegram_webhook_secret,
            )
        )
    assert raised.value.status_code == 401
