from aiogram import Bot, Dispatcher, types

from app.core.config import Settings


async def configure_telegram_bots(
    *,
    config: Settings,
    main_bot: Bot,
    admin_bot: Bot,
    main_dispatcher: Dispatcher,
    admin_dispatcher: Dispatcher,
) -> None:
    base_url = config.WEBHOOK_URL.rstrip("/")
    await main_bot.set_webhook(
        url=f"{base_url}/webhook/main",
        drop_pending_updates=False,
        secret_token=config.main_telegram_webhook_secret,
        allowed_updates=main_dispatcher.resolve_used_update_types(),
    )
    await admin_bot.set_webhook(
        url=f"{base_url}/webhook/admin",
        drop_pending_updates=False,
        secret_token=config.admin_telegram_webhook_secret,
        allowed_updates=admin_dispatcher.resolve_used_update_types(),
    )
    await main_bot.set_my_commands(
        [types.BotCommand(command="start", description="Open Keshepool")]
    )
    await main_bot.set_chat_menu_button(
        menu_button=types.MenuButtonWebApp(
            text="Open Keshepool",
            web_app=types.WebAppInfo(url=config.WEB_APP_URL),
        )
    )
    await admin_bot.set_my_commands(
        [types.BotCommand(command="start", description="Open Admin Panel")]
    )
    await admin_bot.set_chat_menu_button(menu_button=types.MenuButtonCommands())
