import json
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

    if not user.get("id"):
        raise HTTPException(status_code=401, detail="Telegram user id is missing.")
    return user


async def ensure_user_from_telegram_init(
    db: AsyncSession,
    telegram_data: Dict[str, Any],
    referrer_telegram_id: Optional[str] = None,
) -> User:
    telegram_user = parse_telegram_user(telegram_data)
    telegram_id = str(telegram_user["id"])

    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalars().first()
    is_new = user is None

    if is_new:
        user = User(telegram_id=telegram_id)
        db.add(user)

    user.username = telegram_user.get("username")
    user.first_name = telegram_user.get("first_name")
    user.last_name = telegram_user.get("last_name")
    user.language_code = telegram_user.get("language_code")
    user.photo_url = telegram_user.get("photo_url")
    user.is_premium = bool(telegram_user.get("is_premium", False))
    
    current_time = utcnow()
    if not user.last_seen_at or (current_time - user.last_seen_at).total_seconds() > 300:
        user.last_seen_at = current_time

    if telegram_id in settings.admin_ids:
        user.role = "admin"

    if is_new and referrer_telegram_id and referrer_telegram_id != telegram_id:
        referrer_result = await db.execute(select(User).where(User.telegram_id == referrer_telegram_id))
        referrer = referrer_result.scalars().first()
        if referrer:
            user.referrer_id = referrer.id

    await db.flush()

    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    if not wallet:
        db.add(Wallet(user_id=user.id, balance=0))

    await db.commit()
    await db.refresh(user)
    return user