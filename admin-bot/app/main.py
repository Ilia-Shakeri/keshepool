# admin-bot/app/main.py

import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.handlers.admin import admin_router
from app.services.scheduler import start_scheduler
from app.core.config import settings
from app.handlers.products_admin import products_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(token=settings.ADMIN_BOT_TOKEN)
    dp = Dispatcher()

    # Register routers — admin_router was duplicated here, causing the crash
    dp.include_router(admin_router)
    dp.include_router(products_router)

    scheduler = start_scheduler(bot)

    logger.info("Aegis Node Admin Bot initialized. Engaging stealth mode.")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())