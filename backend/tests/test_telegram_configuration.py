import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.core.config import settings
from app import main
from app.services.telegram_configuration import configure_telegram_bots


def test_configuration_uses_split_secrets_and_explicit_updates() -> None:
    main_bot = SimpleNamespace(
        set_webhook=AsyncMock(),
        set_my_commands=AsyncMock(),
        set_chat_menu_button=AsyncMock(),
    )
    admin_bot = SimpleNamespace(
        set_webhook=AsyncMock(),
        set_my_commands=AsyncMock(),
        set_chat_menu_button=AsyncMock(),
    )
    main_dispatcher = SimpleNamespace(resolve_used_update_types=lambda: ["message"])
    admin_dispatcher = SimpleNamespace(
        resolve_used_update_types=lambda: ["message", "callback_query"]
    )

    asyncio.run(
        configure_telegram_bots(
            config=settings,
            main_bot=main_bot,
            admin_bot=admin_bot,
            main_dispatcher=main_dispatcher,
            admin_dispatcher=admin_dispatcher,
        )
    )

    assert main_bot.set_webhook.await_args.kwargs["secret_token"] == settings.main_telegram_webhook_secret
    assert admin_bot.set_webhook.await_args.kwargs["secret_token"] == settings.admin_telegram_webhook_secret
    assert main_bot.set_webhook.await_args.kwargs["allowed_updates"] == ["message"]
    assert admin_bot.set_webhook.await_args.kwargs["allowed_updates"] == [
        "message",
        "callback_query",
    ]


def test_api_lifespan_has_no_telegram_configuration_calls() -> None:
    source = inspect.getsource(main.lifespan)
    assert ".set_webhook" not in source
    assert ".set_my_commands" not in source
    assert ".set_chat_menu_button" not in source
