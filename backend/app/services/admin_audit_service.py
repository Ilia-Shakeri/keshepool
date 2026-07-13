from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import AdminAuditLog


_SENSITIVE_KEY_PARTS = (
    "credential",
    "password",
    "secret",
    "token",
    "private_key",
    "wallet_address",
)


def _safe_value(value: Any, *, key: str = "") -> Any:
    normalized_key = key.lower()
    if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(child_key): _safe_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item, key=key) for item in value]
    return str(value)


async def add_admin_audit(
    session: AsyncSession,
    *,
    actor_telegram_id: int | str,
    action: str,
    target_type: str,
    target_id: int | str | None = None,
    details: Mapping[str, Any] | None = None,
) -> AdminAuditLog:
    row = AdminAuditLog(
        actor_telegram_id=str(actor_telegram_id),
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=_safe_value(details or {}),
    )
    session.add(row)
    await session.flush()
    return row


async def record_admin_audit(**kwargs: Any) -> AdminAuditLog:
    async with AsyncSessionLocal() as session:
        row = await add_admin_audit(session, **kwargs)
        await session.commit()
        return row
