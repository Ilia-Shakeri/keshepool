import logging
from typing import Dict

from aiogram import Bot
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import current_user
from app.core.config import settings
from app.core.database import get_db
from app.models import CashoutRequest, CashoutRequestStatus, User
from app.services.cache_service import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cashout", tags=["cashout"])

ALLOWED_PLATFORMS = {
    "upwork",
    "fiverr",
    "freelancer",
    "toptal",
    "guru",
    "peopleperhour",
    "linkedin",
    "paypal",
    "payoneer",
    "wise",
    "stripe",
    "crypto_exchange",
    "other",
}

PLATFORM_LIST = [
    {"value": "upwork", "label": "Upwork"},
    {"value": "fiverr", "label": "Fiverr"},
    {"value": "freelancer", "label": "Freelancer"},
    {"value": "toptal", "label": "Toptal"},
    {"value": "guru", "label": "Guru"},
    {"value": "peopleperhour", "label": "PeoplePerHour"},
    {"value": "linkedin", "label": "LinkedIn"},
    {"value": "paypal", "label": "PayPal"},
    {"value": "payoneer", "label": "Payoneer"},
    {"value": "wise", "label": "Wise"},
    {"value": "stripe", "label": "Stripe"},
    {"value": "crypto_exchange", "label": "Crypto Exchange"},
    {"value": "other", "label": "سایر (Other)"},
]


class CashoutRequestCreate(BaseModel):
    source_platform: str = Field(min_length=1, max_length=100)
    custom_source: str | None = Field(default=None, max_length=200)
    details_text: str = Field(min_length=10, max_length=2000)

    @field_validator("source_platform")
    @classmethod
    def validate_platform(cls, value: str) -> str:
        normalised = value.lower().strip()
        if normalised not in ALLOWED_PLATFORMS:
            raise ValueError(f"Unsupported platform.")
        return normalised

    @field_validator("details_text")
    @classmethod
    def validate_details(cls, value: str) -> str:
        clean_value = value.strip()
        if len(clean_value) < 10:
            raise ValueError("details_text must contain at least 10 non-space characters.")
        return clean_value

    @model_validator(mode="after")
    def require_custom_source_when_other(self):
        if self.source_platform == "other" and not (
            self.custom_source and self.custom_source.strip()
        ):
            raise ValueError("custom_source is required when source_platform is 'other'.")
        self.custom_source = self.custom_source.strip() if self.custom_source else None
        return self


async def _notify_admins(
    user: User,
    request_id: int,
    platform: str,
    custom: str | None,
    details: str,
) -> None:
    """Dispatch a Telegram alert to the admin group for every new cashout request."""
    if not settings.ADMIN_GROUP_CHAT_ID or not settings.ADMIN_BOT_TOKEN:
        return

    display_platform = custom if (platform == "other" and custom) else platform
    telegram_mention = f"@{user.username}" if user.username else f"ID:{user.telegram_id}"

    message = (
        "💵 New Foreign Income Cashout Request\n\n"
        f"👤 User: {telegram_mention}\n"
        f"🔢 Request ID: #{request_id}\n"
        f"🏦 Platform: {display_platform}\n\n"
        f"📋 Details:\n{details[:500]}{'...' if len(details) > 500 else ''}"
    )

    bot = Bot(token=settings.ADMIN_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=settings.ADMIN_GROUP_CHAT_ID,
            text=message,
        )
    finally:
        await bot.session.close()


@router.post("")
async def create_cashout_request(
    payload: CashoutRequestCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 5 cashout submissions per user per hour
    rate_limit = await check_rate_limit(
        "cashout",
        user.telegram_id,
        limit=5,
        window_seconds=3600,
    )
    if not rate_limit.allowed:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    cashout = CashoutRequest(
        user_id=user.id,
        source_platform=payload.source_platform,
        custom_source=payload.custom_source,
        details_text=payload.details_text,
        status=CashoutRequestStatus.PENDING,
    )
    db.add(cashout)
    await db.commit()
    await db.refresh(cashout)

    try:
        await _notify_admins(
            user=user,
            request_id=cashout.id,
            platform=payload.source_platform,
            custom=payload.custom_source,
            details=payload.details_text,
        )
    except Exception:
        # Admin notification failure must never cascade to the user
        logger.exception("Admin notification failed for cashout request #%d", cashout.id)

    return {
        "status": "submitted",
        "requestId": cashout.id,
        "message": "درخواست شما با موفقیت ثبت شد. تیم ما با شما تماس خواهد گرفت.",
    }


@router.get("/platforms")
async def list_platforms(_: User = Depends(current_user)) -> Dict[str, Any]:
    return {"platforms": PLATFORM_LIST}
