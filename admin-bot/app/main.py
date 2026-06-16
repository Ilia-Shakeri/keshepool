import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.handlers.admin import admin_router
from app.services.scheduler import start_scheduler
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Token is guaranteed to exist due to Pydantic validation on startup
    bot = Bot(token=settings.ADMIN_BOT_TOKEN)
    dp = Dispatcher()

    # Register routers
    dp.include_router(admin_router)

    # Initialize the reporting engine
    scheduler = start_scheduler(bot)

    logger.info("Aegis Node Admin Bot initialized. Engaging stealth mode.")
    
    try:
        # Drop pending updates to avoid processing old messages on restart
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())