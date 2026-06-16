from aiogram.filters import BaseFilter
from aiogram.types import Message
from app.core.config import settings

# Parse comma-separated admin IDs directly from the validated settings
ADMIN_IDS = [int(x.strip()) for x in settings.ADMIN_TELEGRAM_IDS.split(",") if x.strip()]

class IsAdminFilter(BaseFilter):
    """
    Stealth filter: Drops requests from any user not explicitly defined in the settings.
    """
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ADMIN_IDS