from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message
from app.core.config import settings

class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        return str(user.id) in settings.admin_ids