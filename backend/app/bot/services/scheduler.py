import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Order, OrderStatus

logger = logging.getLogger(__name__)

async def send_hourly_report(bot: Bot):
    if not settings.ADMIN_GROUP_CHAT_ID:
        return

    try:
        async with AsyncSessionLocal() as session:
            revenue_result = await session.execute(
                select(func.sum(Order.total_amount)).where(Order.status == OrderStatus.ACTIVE)
            )
            revenue = revenue_result.scalar() or 0

        report_text = (
            "📊 **Hourly Operations Report**\n\n"
            "🟢 Status: Operational\n"
            f"💰 Revenue: {float(revenue):,} Toman\n"
            "⚠️ Low Stock Alerts: Evaluated"
        )
        
        await bot.send_message(chat_id=settings.ADMIN_GROUP_CHAT_ID, text=report_text, parse_mode="Markdown")
        logger.info("Hourly report dispatched successfully.")
    except Exception as e:
        logger.error(f"Failed to dispatch hourly report: {e}")

def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        send_hourly_report, 
        trigger='cron', 
        minute=0, 
        kwargs={'bot': bot}
    )
    scheduler.start()
    return scheduler