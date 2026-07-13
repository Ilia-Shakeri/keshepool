import logging

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.core.config import settings

logger = logging.getLogger(__name__)


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False

        chat = getattr(event, "chat", None)
        if isinstance(event, CallbackQuery):
            chat = getattr(getattr(event, "message", None), "chat", None)

        chat_id = str(getattr(chat, "id", ""))
        chat_type = getattr(chat, "type", "")

        # Every admin action requires an explicit user allowlist entry.
        if str(user.id) not in settings.admin_ids:
            return False

        if chat_type == "private":
            return True

        # Group access also requires the configured chat and a current admin role.
        if (
            chat_type not in {"group", "supergroup"}
            or not settings.ADMIN_GROUP_CHAT_ID
            or chat_id != str(settings.ADMIN_GROUP_CHAT_ID)
        ):
            return False

        bot = getattr(event, "bot", None)
        if bot is None:
            logger.warning("Admin authorization denied because the bot context is unavailable.")
            return False

        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user.id)
        except TelegramAPIError as exc:
            logger.warning(
                "Admin authorization denied because group membership could not be verified: %s",
                type(exc).__name__,
            )
            return False

        return member.status in {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
