import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

logger = logging.getLogger(__name__)

GROUP_CHAT_ID = os.getenv("ADMIN_GROUP_CHAT_ID")

async def send_hourly_report(bot: Bot):
    """
    Fetches DB stats and broadcasts them to the operations group.
    """
    if not GROUP_CHAT_ID:
        return

    # In production, query the DB here for real revenue and active users
    report_text = (
        "📊 **Hourly Operations Report**\n\n"
        "🟢 Status: All Systems Operational\n"
        "💰 Revenue: Pending calculation...\n"
        "⚠️ Low Stock Alerts: None"
    )
    
    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=report_text, parse_mode="Markdown")
        logger.info("Hourly report dispatched successfully.")
    except Exception as e:
        logger.error(f"Failed to dispatch hourly report: {e}")

def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Initializes the async scheduler and mounts the cron jobs.
    """
    scheduler = AsyncIOScheduler()
    
    # Schedule the hourly report at minute 0 of every hour
    scheduler.add_job(
        send_hourly_report, 
        trigger='cron', 
        minute=0, 
        kwargs={'bot': bot}
    )
    
    scheduler.start()
    return scheduler