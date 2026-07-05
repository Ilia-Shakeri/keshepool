from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from app.core.config import settings

KESHEPOOL_ADMIN_GROUP_ID = "-5301036860"


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

        # Allow every member of the dedicated admin group to use admin commands there.
        if chat_id == KESHEPOOL_ADMIN_GROUP_ID:
            return True

        # Allow only explicitly listed direct-message admins outside the group.
        if chat_type == "private" and str(user.id) in settings.admin_direct_ids:
            return True

        return False
