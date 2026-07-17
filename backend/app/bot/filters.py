import logging

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.core.config import settings

logger = logging.getLogger(__name__)


def _log_rejection(reason: str) -> None:
    logger.info("Admin authorization rejected.", extra={"rejection_reason": reason})


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            _log_rejection("missing_from_user")
            return False

        chat = getattr(event, "chat", None)
        if isinstance(event, CallbackQuery):
            chat = getattr(getattr(event, "message", None), "chat", None)

        chat_id = str(getattr(chat, "id", ""))
        chat_type = getattr(chat, "type", "")

        # Every admin action requires an explicit user allowlist entry.
        if str(user.id) not in settings.admin_ids:
            _log_rejection("user_not_allowlisted")
            return False

        if chat_type == "private":
            return True

        # Group access also requires the configured chat and a current admin role.
        if chat_type not in {"group", "supergroup"}:
            _log_rejection("wrong_chat")
            return False

        if not settings.ADMIN_GROUP_CHAT_ID:
            _log_rejection("group_not_configured")
            return False

        if chat_id != str(settings.ADMIN_GROUP_CHAT_ID):
            _log_rejection("wrong_chat")
            return False

        bot = getattr(event, "bot", None)
        if bot is None:
            _log_rejection("bot_context_missing")
            return False

        try:
            member = await bot.get_chat_member(chat_id=int(chat_id), user_id=user.id)
        except TelegramAPIError as exc:
            logger.info(
                "Admin authorization rejected.",
                extra={
                    "rejection_reason": "membership_check_failed",
                    "exception_class": type(exc).__name__,
                },
            )
            return False

        allowed = member.status in {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
        if not allowed:
            _log_rejection("user_not_group_admin")
        return allowed
