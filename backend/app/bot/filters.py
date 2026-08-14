import logging

from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.admin_authorization_service import effective_roles
from app.services.admin_audit_service import record_admin_audit

logger = logging.getLogger(__name__)


async def _record_authorization(event: Message | CallbackQuery, outcome: str, reason: str | None = None) -> None:
    user = getattr(event, "from_user", None)
    actor = getattr(user, "id", "unknown")
    try:
        await record_admin_audit(
            actor_telegram_id=actor,
            action="admin.authorization",
            target_type="admin_ingress",
            outcome=outcome,
            reason=reason,
        )
    except Exception as exc:
        logger.warning(
            "Admin authorization audit write failed.",
            extra={"exception_class": type(exc).__name__},
        )


async def _reject(event: Message | CallbackQuery, reason: str) -> bool:
    logger.info("Admin authorization rejected.", extra={"rejection_reason": reason})
    await _record_authorization(event, "rejected", reason)
    return False


async def _allow(event: Message | CallbackQuery) -> bool:
    await _record_authorization(event, "success")
    return True


async def _has_durable_role(telegram_id: int) -> bool:
    async with AsyncSessionLocal() as session:
        return bool(await effective_roles(session, telegram_id))


async def _roles_for_admin(telegram_id: int) -> frozenset[str]:
    if (
        settings.ADMIN_ENV_BREAK_GLASS_ENABLED
        and str(telegram_id) in settings.admin_ids
    ):
        return frozenset({"superadmin"})
    async with AsyncSessionLocal() as session:
        return await effective_roles(session, telegram_id)


class HasAdminRoleFilter(BaseFilter):
    def __init__(self, *roles: str):
        self.roles = frozenset(roles)

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        if not settings.ADMIN_RBAC_ENABLED:
            return True
        user = getattr(event, "from_user", None)
        if user is None:
            return await _reject(event, "missing_from_user")
        try:
            roles = await _roles_for_admin(user.id)
        except Exception as exc:
            logger.warning(
                "Admin role lookup failed closed.",
                extra={"exception_class": type(exc).__name__},
            )
            return await _reject(event, "role_lookup_failed")
        allowed = "superadmin" in roles or not roles.isdisjoint(self.roles)
        if not allowed:
            return await _reject(event, "role_not_permitted")
        return allowed


class IsAdminFilter(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return await _reject(event, "missing_from_user")

        chat = getattr(event, "chat", None)
        if isinstance(event, CallbackQuery):
            chat = getattr(getattr(event, "message", None), "chat", None)

        chat_id = str(getattr(chat, "id", ""))
        chat_type = getattr(chat, "type", "")

        has_env_break_glass = (
            settings.ADMIN_ENV_BREAK_GLASS_ENABLED
            and str(user.id) in settings.admin_ids
        )
        if not has_env_break_glass:
            if not settings.ADMIN_RBAC_ENABLED:
                return await _reject(event, "user_not_allowlisted")
            try:
                has_role = await _has_durable_role(user.id)
            except Exception as exc:
                logger.warning(
                    "Durable admin authorization failed closed.",
                    extra={"exception_class": type(exc).__name__},
                )
                has_role = False
            if not has_role:
                return await _reject(event, "user_has_no_active_role")

        if chat_type == "private":
            return await _allow(event)

        # Group access always requires the one configured chat.
        if chat_type not in {"group", "supergroup"}:
            return await _reject(event, "wrong_chat")

        if not settings.ADMIN_GROUP_CHAT_ID:
            return await _reject(event, "group_not_configured")

        if chat_id != str(settings.ADMIN_GROUP_CHAT_ID):
            return await _reject(event, "wrong_chat")

        if not settings.ADMIN_REQUIRE_GROUP_ADMIN:
            return await _allow(event)

        bot = getattr(event, "bot", None)
        if bot is None:
            return await _reject(event, "bot_context_missing")

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
            await _record_authorization(event, "rejected", "membership_check_failed")
            return False

        allowed = member.status in {
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }
        if not allowed:
            await _record_authorization(event, "rejected", "user_not_group_admin")
        else:
            await _record_authorization(event, "success")
        return allowed
