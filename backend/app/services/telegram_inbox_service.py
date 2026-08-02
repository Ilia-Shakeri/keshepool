from datetime import timedelta
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramUpdateInbox, utcnow


BotType = Literal["main", "admin"]


async def enqueue_update(
    db: AsyncSession,
    *,
    bot_type: BotType,
    update_id: int,
    payload: dict[str, Any],
) -> bool:
    statement = (
        pg_insert(TelegramUpdateInbox)
        .values(
            bot_type=bot_type,
            update_id=update_id,
            payload=payload,
            status="pending",
            attempts=0,
            next_attempt_at=utcnow(),
        )
        .on_conflict_do_nothing(constraint="uq_telegram_update_bot_id")
        .returning(TelegramUpdateInbox.id)
    )
    inserted_id = (await db.execute(statement)).scalar_one_or_none()
    await db.commit()
    return inserted_id is not None


async def claim_updates(
    db: AsyncSession,
    *,
    limit: int,
    stale_after_seconds: int,
) -> list[TelegramUpdateInbox]:
    now = utcnow()
    stale_before = now - timedelta(seconds=stale_after_seconds)
    statement = (
        select(TelegramUpdateInbox)
        .where(
            or_(
                (
                    TelegramUpdateInbox.status.in_(("pending", "retry"))
                    & (TelegramUpdateInbox.next_attempt_at <= now)
                ),
                (
                    (TelegramUpdateInbox.status == "processing")
                    & (TelegramUpdateInbox.locked_at < stale_before)
                ),
            )
        )
        .order_by(TelegramUpdateInbox.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    items = list((await db.execute(statement)).scalars().all())
    for item in items:
        item.status = "processing"
        item.attempts += 1
        item.locked_at = now
        item.updated_at = now
    await db.commit()
    return items


async def mark_update_done(db: AsyncSession, inbox_id: int) -> None:
    item = await db.get(TelegramUpdateInbox, inbox_id, with_for_update=True)
    if item is None:
        return
    now = utcnow()
    item.status = "done"
    item.processed_at = now
    item.locked_at = None
    item.last_error = None
    item.updated_at = now
    await db.commit()


async def mark_update_failed(
    db: AsyncSession,
    inbox_id: int,
    *,
    max_attempts: int,
    retry_delay_seconds: int,
    error_class: str,
) -> None:
    item = await db.get(TelegramUpdateInbox, inbox_id, with_for_update=True)
    if item is None:
        return
    now = utcnow()
    item.status = "failed" if item.attempts >= max_attempts else "retry"
    item.next_attempt_at = now + timedelta(seconds=retry_delay_seconds)
    item.locked_at = None
    item.last_error = error_class[:200]
    item.updated_at = now
    await db.commit()
