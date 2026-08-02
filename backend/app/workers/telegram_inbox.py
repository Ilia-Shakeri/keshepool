import asyncio
import logging

from aiogram import types

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.main import admin_bot, admin_dp, bot, dp
from app.services.telegram_inbox_service import (
    claim_updates,
    mark_update_done,
    mark_update_failed,
)


logger = logging.getLogger(__name__)


async def dispatch_claimed_update(item) -> None:
    try:
        update = types.Update(**item.payload)
        if item.bot_type == "admin":
            await admin_dp.feed_update(bot=admin_bot, update=update)
        else:
            await dp.feed_update(bot=bot, update=update)
    except Exception as exc:
        logger.error(
            "Telegram inbox dispatch failed.",
            extra={
                "bot_type": item.bot_type,
                "telegram_update_id": item.update_id,
                "inbox_id": item.id,
                "exception_class": type(exc).__name__,
            },
        )
        async with AsyncSessionLocal() as session:
            await mark_update_failed(
                session,
                item.id,
                max_attempts=settings.TELEGRAM_INBOX_MAX_ATTEMPTS,
                retry_delay_seconds=settings.TELEGRAM_INBOX_RETRY_SECONDS,
                error_class=type(exc).__name__,
            )
        return

    async with AsyncSessionLocal() as session:
        await mark_update_done(session, item.id)


async def run_worker() -> None:
    try:
        while True:
            async with AsyncSessionLocal() as session:
                items = await claim_updates(
                    session,
                    limit=settings.TELEGRAM_INBOX_BATCH_SIZE,
                    stale_after_seconds=settings.TELEGRAM_INBOX_STALE_SECONDS,
                )
            if not items:
                await asyncio.sleep(settings.TELEGRAM_INBOX_POLL_SECONDS)
                continue
            for item in items:
                await dispatch_claimed_update(item)
    finally:
        await bot.session.close()
        await admin_bot.session.close()
        await dp.storage.close()
        await admin_dp.storage.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_worker())
