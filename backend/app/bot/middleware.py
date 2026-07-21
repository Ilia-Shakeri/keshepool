import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import User

logger = logging.getLogger(__name__)


def _telegram_user_id(update: Update) -> str | None:
    event = update.event
    from_user = getattr(event, "from_user", None)
    return str(from_user.id) if from_user is not None else None


class BlockBannedUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Update):
            return await handler(event, data)

        telegram_id = _telegram_user_id(event)
        if telegram_id is None:
            return await handler(event, data)

        try:
            async with AsyncSessionLocal() as session:
                is_banned = await session.scalar(
                    select(User.is_banned).where(User.telegram_id == telegram_id)
                )
        except Exception as exc:
            logger.warning(
                "User access check failed; bot update blocked.",
                extra={"exception_class": type(exc).__name__},
            )
            return None

        if is_banned:
            logger.info("Blocked banned bot user.", extra={"telegram_user_id": telegram_id})
            return None
        return await handler(event, data)
