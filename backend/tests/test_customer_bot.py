import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram.types import InlineKeyboardMarkup

from app.bot.handlers.customer import customer_start
from app.core.config import settings


def test_customer_private_start_has_web_app_button_in_persian():
    message = SimpleNamespace(
        from_user=SimpleNamespace(language_code="fa"),
        answer=AsyncMock(),
    )
    asyncio.run(customer_start(message))
    message.answer.assert_awaited_once()
    text, = message.answer.await_args.args
    markup = message.answer.await_args.kwargs["reply_markup"]
    assert "کش‌پول" in text
    assert isinstance(markup, InlineKeyboardMarkup)
    assert markup.inline_keyboard[0][0].web_app.url == settings.WEB_APP_URL


def test_customer_private_start_has_professional_english_fallback():
    message = SimpleNamespace(
        from_user=SimpleNamespace(language_code="en"),
        answer=AsyncMock(),
    )
    asyncio.run(customer_start(message))
    assert "Welcome to Keshepool" in message.answer.await_args.args[0]
