import html
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import InventoryItem, ItemStatus, Product, ProductVariant
from app.bot.services.daily_report_settings import is_daily_report_enabled
from app.services.card_transfer_service import deliver_card_transfer_notifications

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 3


async def _check_low_stock(session) -> list[str]:
    """Return warning lines for active variants with stock at or below the threshold.

    Uses a LEFT JOIN so variants with zero available items are also included.
    """
    checked_at = datetime.now(timezone.utc)
    query = (
        select(
            ProductVariant.id.label("vid"),
            ProductVariant.duration.label("dur"),
            func.count(InventoryItem.id).label("qty"),
        )
        .join(Product, Product.id == ProductVariant.product_id)
        .outerjoin(
            InventoryItem,
            and_(
                InventoryItem.variant_id == ProductVariant.id,
                InventoryItem.status == ItemStatus.AVAILABLE,
                (InventoryItem.expires_at.is_(None) | (InventoryItem.expires_at > checked_at)),
            ),
        )
        .where(
            Product.is_active.is_(True),
            ProductVariant.is_active.is_(True),
        )
        .group_by(ProductVariant.id, ProductVariant.duration)
        .having(func.count(InventoryItem.id) <= LOW_STOCK_THRESHOLD)
    )
    result = await session.execute(query)
    rows = result.all()
    return [
        f"⚠️ {html.escape(str(row.vid))} / "
        f"{html.escape(str(row.dur))}: {int(row.qty)} remaining"
        for row in rows
    ]


async def send_daily_report(bot: Bot):
    if not settings.ADMIN_GROUP_CHAT_ID:
        return

    try:
        if not await is_daily_report_enabled():
            logger.info("Daily report is disabled.")
            return

        # Import here to avoid circular imports at module load time
        from app.bot.handlers.admin_panel import build_report_text

        report_text = await build_report_text(settings.ADMIN_REPORT_LANGUAGE)

        async with AsyncSessionLocal() as session:
            low_stock_warnings = await _check_low_stock(session)

        if low_stock_warnings:
            report_text += "\n\n📉 <b>Low Stock Alerts</b>\n" + "\n".join(low_stock_warnings[:10])

        await bot.send_message(
            chat_id=settings.ADMIN_GROUP_CHAT_ID,
            text=report_text,
            parse_mode="HTML",
        )
        logger.info("Daily report dispatched successfully.")
    except Exception:
        logger.exception("Failed to dispatch daily report.")
        raise


async def retry_card_transfer_notifications(bot: Bot):
    if not settings.card_to_card_ready:
        return
    try:
        await deliver_card_transfer_notifications(bot, limit=20)
    except Exception:
        logger.exception("Card transfer notification retry failed.")


def start_scheduler(bot: Bot) -> AsyncIOScheduler:
    report_timezone = ZoneInfo(settings.TZ)
    scheduler = AsyncIOScheduler(timezone=report_timezone)
    scheduler.add_job(
        send_daily_report,
        trigger="cron",
        hour=23,
        minute=59,
        timezone=report_timezone,
        kwargs={"bot": bot},
        id="daily-admin-report",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        retry_card_transfer_notifications,
        trigger="interval",
        seconds=60,
        kwargs={"bot": bot},
        id="card-transfer-admin-delivery",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    return scheduler
