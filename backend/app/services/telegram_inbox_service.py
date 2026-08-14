from datetime import timedelta
from secrets import token_urlsafe
from typing import Any, Literal

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramUpdateInbox, utcnow


BotType = Literal["main", "admin"]
MAX_ATTEMPTS_ERROR = "MaxAttemptsExceeded"


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
    max_attempts: int,
) -> list[TelegramUpdateInbox]:
    if limit < 1:
        raise ValueError("limit must be positive")
    if stale_after_seconds < 1:
        raise ValueError("stale_after_seconds must be positive")
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    now = utcnow()
    stale_before = now - timedelta(seconds=stale_after_seconds)
    due_or_stale = or_(
        and_(
            TelegramUpdateInbox.status.in_(("pending", "retry")),
            TelegramUpdateInbox.next_attempt_at <= now,
        ),
        and_(
            TelegramUpdateInbox.status == "processing",
            or_(
                TelegramUpdateInbox.locked_at.is_(None),
                TelegramUpdateInbox.locked_at < stale_before,
            ),
        ),
    )

    # A worker may die on its last allowed attempt. Retire that stale lease
    # instead of leaving it stuck or granting an extra attempt.
    await db.execute(
        update(TelegramUpdateInbox)
        .where(
            TelegramUpdateInbox.attempts >= max_attempts,
            due_or_stale,
        )
        .values(
            status="failed",
            payload={},
            claim_token=None,
            locked_at=None,
            processed_at=now,
            last_error=MAX_ATTEMPTS_ERROR,
            updated_at=now,
        )
    )
    statement = (
        select(TelegramUpdateInbox)
        .where(
            TelegramUpdateInbox.attempts < max_attempts,
            due_or_stale,
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
        item.claim_token = token_urlsafe(32)
        item.processed_at = None
        item.updated_at = now
    await db.commit()
    return items


async def renew_update_claim(
    db: AsyncSession,
    inbox_id: int,
    *,
    claim_token: str,
) -> bool:
    if not claim_token:
        return False
    now = utcnow()
    result = await db.execute(
        update(TelegramUpdateInbox)
        .where(
            TelegramUpdateInbox.id == inbox_id,
            TelegramUpdateInbox.status == "processing",
            TelegramUpdateInbox.claim_token == claim_token,
        )
        .values(locked_at=now, updated_at=now)
    )
    await db.commit()
    return result.rowcount == 1


async def mark_update_done(
    db: AsyncSession,
    inbox_id: int,
    *,
    claim_token: str,
) -> bool:
    if not claim_token:
        return False
    now = utcnow()
    result = await db.execute(
        update(TelegramUpdateInbox)
        .where(
            TelegramUpdateInbox.id == inbox_id,
            TelegramUpdateInbox.status == "processing",
            TelegramUpdateInbox.claim_token == claim_token,
        )
        .values(
            status="done",
            payload={},
            claim_token=None,
            processed_at=now,
            locked_at=None,
            last_error=None,
            updated_at=now,
        )
    )
    await db.commit()
    return result.rowcount == 1


async def mark_update_failed(
    db: AsyncSession,
    inbox_id: int,
    *,
    claim_token: str,
    max_attempts: int,
    retry_delay_seconds: int,
    error_class: str,
) -> bool:
    if not claim_token:
        return False
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if retry_delay_seconds < 1:
        raise ValueError("retry_delay_seconds must be positive")
    now = utcnow()
    claim_matches = and_(
        TelegramUpdateInbox.id == inbox_id,
        TelegramUpdateInbox.status == "processing",
        TelegramUpdateInbox.claim_token == claim_token,
    )
    terminal = await db.execute(
        update(TelegramUpdateInbox)
        .where(claim_matches, TelegramUpdateInbox.attempts >= max_attempts)
        .values(
            status="failed",
            payload={},
            claim_token=None,
            processed_at=now,
            locked_at=None,
            last_error=error_class[:200],
            updated_at=now,
        )
    )
    if terminal.rowcount == 1:
        await db.commit()
        return True

    retry = await db.execute(
        update(TelegramUpdateInbox)
        .where(claim_matches, TelegramUpdateInbox.attempts < max_attempts)
        .values(
            status="retry",
            claim_token=None,
            next_attempt_at=now + timedelta(seconds=retry_delay_seconds),
            processed_at=None,
            locked_at=None,
            last_error=error_class[:200],
            updated_at=now,
        )
    )
    await db.commit()
    return retry.rowcount == 1
