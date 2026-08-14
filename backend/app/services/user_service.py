import json
import re
import secrets
from datetime import timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models import User, Wallet, utcnow


REFERRAL_CODE_PATTERN = re.compile(r"^[0-9a-f]{32}$")
REFERRAL_INSERT_ATTEMPTS = 5


def generate_referral_code() -> str:
    return secrets.token_hex(16)


def normalize_referral_code(value: object) -> str | None:
    if not isinstance(value, str) or not REFERRAL_CODE_PATTERN.fullmatch(value):
        return None
    return value


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
    raw_user_id = user["id"]
    if isinstance(raw_user_id, bool) or not re.fullmatch(
        r"(?:0|[1-9][0-9]{0,19})",
        str(raw_user_id),
    ):
        raise HTTPException(status_code=401, detail="Telegram user id is invalid.")
    return user


async def ensure_user_from_telegram_init(
    db: AsyncSession,
    telegram_data: Dict[str, Any],
    referral_code: Optional[str] = None,
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
    normalized_referral_code = normalize_referral_code(referral_code)
    if attempted_user_insert and normalized_referral_code:
        referrer_result = await db.execute(
            select(User).where(
                User.referral_code == normalized_referral_code,
                User.is_banned.is_(False),
            )
        )
        referrer = referrer_result.scalars().first()
        if referrer and referrer.telegram_id != telegram_id:
            referrer_id = referrer.id

    if attempted_user_insert:
        user_inserted_or_found = False
        for _ in range(REFERRAL_INSERT_ATTEMPTS):
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
                    referral_code=generate_referral_code(),
                    referrer_id=referrer_id,
                    last_seen_at=current_time,
                    created_at=current_time,
                    updated_at=current_time,
                )
                .on_conflict_do_nothing()
                .returning(User.id)
            )
            if insert_result.scalar_one_or_none() is not None:
                user_inserted_or_found = True
                break
            concurrent_user_result = await db.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            if concurrent_user_result.scalars().first() is not None:
                user_inserted_or_found = True
                break
        if not user_inserted_or_found:
            await db.rollback()
            raise HTTPException(status_code=503, detail="Could not allocate a referral code.")

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
