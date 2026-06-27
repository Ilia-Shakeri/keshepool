import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import InventoryItem, ItemStatus, ProductVariant

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 3


async def _check_low_stock(session) -> list[str]:
    """Return warning lines for active variants with stock at or below the threshold.

    Uses a LEFT JOIN so variants with zero available items are also included.
    """
    from sqlalchemy import outerjoin, case, literal

    subq = (
        select(
            ProductVariant.id.label("vid"),
            ProductVariant.duration.label("dur"),
            func.coalesce(
                func.count(
                    case((InventoryItem.status == ItemStatus.AVAILABLE, InventoryItem.id))
                ),
                0,
            ).label("qty"),
        )
        .outerjoin(InventoryItem, InventoryItem.variant_id == ProductVariant.id)
        .where(ProductVariant.is_active.is_(True))
        .group_by(ProductVariant.id, ProductVariant.duration)
        .having(
            func.coalesce(
                func.count(
                    case((InventoryItem.status == ItemStatus.AVAILABLE, InventoryItem.id))
                ),
                0,
            ) < LOW_STOCK_THRESHOLD
        )
    )
    result = await session.execute(subq)
    rows = result.all()
    return [f"⚠️ {row.vid} / {row.dur}: {row.qty} remaining" for row in rows]


async def send_hourly_report(bot: Bot):
    if not settings.ADMIN_GROUP_CHAT_ID:
        return

    try:
        # Import here to avoid circular imports at module load time
        from app.bot.handlers.admin_panel import build_report_text

        report_text = await build_report_text()

        async with AsyncSessionLocal() as session:
            low_stock_warnings = await _check_low_stock(session)

        if low_stock_warnings:
            report_text += "\n\n📉 <b>Low Stock Alerts</b>\n" + "\n".join(low_stock_warnings[:10])

        await bot.send_message(
            chat_id=settings.ADMIN_GROUP_CHAT_ID,
            text=report_text,
            parse_mode="HTML",
        )
        logger.info("Hourly report dispatched successfully.")
    except Exception as exc:
        logger.error("Failed to dispatch hourly report: %s", exc)


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_hourly_report, trigger="cron", minute=0, kwargs={"bot": bot})
    scheduler.start()
    return scheduler
