import re
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import AdminAuditLog


_SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "cashout_details",
    "cookie",
    "credential",
    "init_data",
    "initdata",
    "payment_payload",
    "password",
    "secret",
    "signature",
    "token",
    "private_key",
    "wallet_address",
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"(?:^|[?&])(hash|signature|token|secret|auth_date|query_id)=[^&\s]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
)
_AUDIT_CONTEXT: ContextVar[dict[str, Any]] = ContextVar("admin_audit_context", default={})


@contextmanager
def admin_audit_context(*, update_id: int | None = None, chat_id: int | str | None = None):
    token = _AUDIT_CONTEXT.set(
        {
            "update_id": update_id,
            "chat_id": str(chat_id)[:24] if chat_id is not None else None,
        }
    )
    try:
        yield
    finally:
        _AUDIT_CONTEXT.reset(token)


def _safe_value(value: Any, *, key: str = "") -> Any:
    normalized_key = key.lower()
    if any(part in normalized_key for part in _SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS):
            return "[redacted]"
        return value[:500]
    if value is None or isinstance(value, (bool, int, float)):
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
    outcome: str = "success",
    request_id: str | None = None,
    update_id: int | None = None,
    chat_id: int | str | None = None,
    reason: str | None = None,
    old_values: Mapping[str, Any] | None = None,
    new_values: Mapping[str, Any] | None = None,
) -> AdminAuditLog:
    if outcome not in {"success", "rejected", "failed", "requested"}:
        raise ValueError("Invalid audit outcome.")
    context = _AUDIT_CONTEXT.get()
    row = AdminAuditLog(
        actor_telegram_id=str(actor_telegram_id),
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        outcome=outcome,
        request_id=request_id[:64] if request_id else None,
        update_id=update_id if update_id is not None else context.get("update_id"),
        chat_id=(str(chat_id)[:24] if chat_id is not None else context.get("chat_id")),
        reason=reason[:100] if reason else None,
        old_values=_safe_value(old_values or {}),
        new_values=_safe_value(new_values or {}),
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
