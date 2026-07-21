import json
from datetime import timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import User, Wallet, utcnow


def parse_telegram_user(telegram_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        user_payload = telegram_data.get("user")
        if isinstance(user_payload, str):
            user = json.loads(user_payload)
        elif isinstance(user_payload, dict):
            user = user_payload
        else:
            raise ValueError("Missing Telegram user payload")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Telegram user payload.") from exc

    if "id" not in user or user["id"] in (None, ""):
        raise HTTPException(status_code=401, detail="Telegram user id is missing.")
    return user


async def ensure_user_from_telegram_init(
    db: AsyncSession,
    telegram_data: Dict[str, Any],
    referrer_telegram_id: Optional[str] = None,
) -> User:
    telegram_user = parse_telegram_user(telegram_data)
    telegram_id = str(telegram_user["id"])

    user_result = await db.execute(
        select(User)
        .options(selectinload(User.wallet))
        .where(User.telegram_id == telegram_id)
    )
    user = user_result.scalars().first()
    current_time = utcnow()
    attempted_user_insert = user is None
    if user is not None and user.is_banned:
        raise HTTPException(status_code=403, detail="User access is blocked.")
    referrer_id = None
    if attempted_user_insert and referrer_telegram_id and referrer_telegram_id != telegram_id:
        referrer_result = await db.execute(select(User).where(User.telegram_id == referrer_telegram_id))
        referrer = referrer_result.scalars().first()
        if referrer:
            referrer_id = referrer.id

    if attempted_user_insert:
        insert_result = await db.execute(
            pg_insert(User)
            .values(
                telegram_id=telegram_id,
                username=telegram_user.get("username"),
                first_name=telegram_user.get("first_name"),
                last_name=telegram_user.get("last_name"),
                language_code=telegram_user.get("language_code"),
                photo_url=telegram_user.get("photo_url"),
                is_premium=bool(telegram_user.get("is_premium", False)),
                role="admin" if telegram_id in settings.admin_ids else "user",
                referrer_id=referrer_id,
                last_seen_at=current_time,
                created_at=current_time,
                updated_at=current_time,
            )
            .on_conflict_do_nothing(index_elements=[User.telegram_id])
            .returning(User.id)
        )
        insert_result.scalar_one_or_none()
        user_result = await db.execute(
            select(User)
            .options(selectinload(User.wallet))
            .where(User.telegram_id == telegram_id)
        )
        user = user_result.scalars().one()

    changed = attempted_user_insert
    profile_values = {
        "username": telegram_user.get("username"),
        "first_name": telegram_user.get("first_name"),
        "last_name": telegram_user.get("last_name"),
        "language_code": telegram_user.get("language_code"),
        "photo_url": telegram_user.get("photo_url"),
        "is_premium": bool(telegram_user.get("is_premium", False)),
    }
    for field, value in profile_values.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            changed = True

    last_seen_at = user.last_seen_at
    if last_seen_at is not None and last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    if (
        last_seen_at is None
        or (current_time - last_seen_at).total_seconds()
        >= settings.USER_LAST_SEEN_WRITE_INTERVAL_SECONDS
    ):
        user.last_seen_at = current_time
        changed = True

    if telegram_id in settings.admin_ids and user.role != "admin":
        user.role = "admin"
        changed = True

    if user.wallet is None:
        wallet_result = await db.execute(
            pg_insert(Wallet)
            .values(user_id=user.id, balance=0)
            .on_conflict_do_nothing(index_elements=[Wallet.user_id])
            .returning(Wallet.id)
        )
        if wallet_result.scalar_one_or_none() is not None:
            changed = True

    if changed:
        await db.commit()
    return user
