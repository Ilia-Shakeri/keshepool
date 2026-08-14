import asyncio
import logging

from aiogram import types

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.main import admin_bot, admin_dp, bot, dp
from app.bot.services.scheduler import start_scheduler
from app.models import TelegramUpdateInbox
from app.services.admin_audit_service import admin_audit_context
from app.services.telegram_inbox_service import (
    claim_updates,
    mark_update_done,
    mark_update_failed,
    renew_update_claim,
)


logger = logging.getLogger(__name__)
ClaimHeartbeat = tuple[asyncio.Event, asyncio.Task[None]]


def _admin_chat_id(payload: dict) -> int | str | None:
    message = payload.get("message") or payload.get("edited_message")
    if not isinstance(message, dict):
        callback = payload.get("callback_query")
        message = callback.get("message") if isinstance(callback, dict) else None
    chat = message.get("chat") if isinstance(message, dict) else None
    return chat.get("id") if isinstance(chat, dict) else None


async def _heartbeat_claim(
    inbox_id: int,
    claim_token: str,
    stop: asyncio.Event,
    *,
    interval_seconds: float,
) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            return
        except TimeoutError:
            pass

        try:
            async with AsyncSessionLocal() as session:
                renewed = await renew_update_claim(
                    session,
                    inbox_id,
                    claim_token=claim_token,
                )
        except Exception as exc:
            logger.error(
                "Telegram inbox heartbeat failed.",
                extra={
                    "inbox_id": inbox_id,
                    "exception_class": type(exc).__name__,
                },
            )
            continue

        if not renewed:
            logger.warning(
                "Telegram inbox heartbeat lost its claim fence.",
                extra={"inbox_id": inbox_id},
            )
            return


def _start_claim_heartbeat(item: TelegramUpdateInbox) -> ClaimHeartbeat | None:
    if not item.claim_token:
        return None
    stop = asyncio.Event()
    interval_seconds = max(1.0, settings.TELEGRAM_INBOX_STALE_SECONDS / 3)
    task = asyncio.create_task(
        _heartbeat_claim(
            item.id,
            item.claim_token,
            stop,
            interval_seconds=interval_seconds,
        )
    )
    return stop, task


async def _stop_claim_heartbeat(heartbeat: ClaimHeartbeat | None) -> None:
    if heartbeat is None:
        return
    stop, task = heartbeat
    stop.set()
    await task


async def _save_dispatch_result(
    item: TelegramUpdateInbox,
    *,
    error_class: str | None,
) -> None:
    if not item.claim_token:
        logger.error(
            "Telegram inbox row has no claim fence.",
            extra={"inbox_id": item.id},
        )
        return

    try:
        async with AsyncSessionLocal() as session:
            if error_class is None:
                saved = await mark_update_done(
                    session,
                    item.id,
                    claim_token=item.claim_token,
                )
            else:
                saved = await mark_update_failed(
                    session,
                    item.id,
                    claim_token=item.claim_token,
                    max_attempts=settings.TELEGRAM_INBOX_MAX_ATTEMPTS,
                    retry_delay_seconds=settings.TELEGRAM_INBOX_RETRY_SECONDS,
                    error_class=error_class,
                )
    except Exception as exc:
        logger.error(
            "Telegram inbox result save failed.",
            extra={
                "inbox_id": item.id,
                "exception_class": type(exc).__name__,
            },
        )
        return

    if not saved:
        logger.warning(
            "Telegram inbox result rejected by claim fence.",
            extra={"inbox_id": item.id},
        )


async def dispatch_claimed_update(
    item: TelegramUpdateInbox,
    *,
    heartbeat: ClaimHeartbeat | None = None,
) -> None:
    if not item.claim_token:
        logger.error(
            "Telegram inbox row has no claim fence.",
            extra={"inbox_id": item.id},
        )
        return

    active_heartbeat = heartbeat or _start_claim_heartbeat(item)
    error_class: str | None = None
    try:
        telegram_update = types.Update(**item.payload)
        if item.bot_type == "admin":
            with admin_audit_context(
                update_id=item.update_id,
                chat_id=_admin_chat_id(item.payload),
            ):
                await admin_dp.feed_update(bot=admin_bot, update=telegram_update)
        else:
            await dp.feed_update(bot=bot, update=telegram_update)
    except Exception as exc:
        error_class = type(exc).__name__
        logger.error(
            "Telegram inbox dispatch failed.",
            extra={
                "bot_type": item.bot_type,
                "telegram_update_id": item.update_id,
                "inbox_id": item.id,
                "exception_class": error_class,
            },
        )
    finally:
        await _stop_claim_heartbeat(active_heartbeat)

    await _save_dispatch_result(item, error_class=error_class)


async def run_worker() -> None:
    scheduler = (
        start_scheduler(admin_bot)
        if settings.TELEGRAM_BOT_MODE != "disabled"
        else None
    )
    try:
        while True:
            async with AsyncSessionLocal() as session:
                items = await claim_updates(
                    session,
                    limit=settings.TELEGRAM_INBOX_BATCH_SIZE,
                    stale_after_seconds=settings.TELEGRAM_INBOX_STALE_SECONDS,
                    max_attempts=settings.TELEGRAM_INBOX_MAX_ATTEMPTS,
                )
            if not items:
                await asyncio.sleep(settings.TELEGRAM_INBOX_POLL_SECONDS)
                continue
            heartbeats = {
                item.id: _start_claim_heartbeat(item)
                for item in items
            }
            try:
                for item in items:
                    await dispatch_claimed_update(
                        item,
                        heartbeat=heartbeats[item.id],
                    )
            finally:
                await asyncio.gather(
                    *(
                        _stop_claim_heartbeat(heartbeat)
                        for heartbeat in heartbeats.values()
                    )
                )
    finally:
        if scheduler is not None:
            try:
                scheduler.shutdown(wait=False)
            except Exception:
                logger.exception("Scheduler shutdown failed.")
        await bot.session.close()
        await admin_bot.session.close()
        await dp.storage.close()
        await admin_dp.storage.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_worker())
