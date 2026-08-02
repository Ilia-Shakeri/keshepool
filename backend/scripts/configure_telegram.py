import asyncio

from app.core.config import settings
from app.main import admin_bot, admin_dp, bot, dp
from app.services.telegram_configuration import configure_telegram_bots


async def main() -> None:
    if settings.TELEGRAM_BOT_MODE != "webhook":
        raise RuntimeError("Telegram configuration requires webhook mode.")
    try:
        await configure_telegram_bots(
            config=settings,
            main_bot=bot,
            admin_bot=admin_bot,
            main_dispatcher=dp,
            admin_dispatcher=admin_dp,
        )
        print("Telegram webhook and menu configuration completed.")
    finally:
        await bot.session.close()
        await admin_bot.session.close()
        await dp.storage.close()
        await admin_dp.storage.close()


if __name__ == "__main__":
    asyncio.run(main())
