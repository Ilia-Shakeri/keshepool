import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Final

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    AdminActionNonce,
    AdminApprovalRequest,
    AdminApprovalVote,
    AdminIdentity,
    AdminRoleGrant,
)


ADMIN_ROLES: Final = frozenset({"superadmin", "finance", "catalog", "support", "auditor"})
ACTION_ROLES: Final = {
    "wallet.adjust": frozenset({"superadmin", "finance"}),
    "rate.override": frozenset({"superadmin", "finance"}),
    "catalog.mass_remove": frozenset({"superadmin", "catalog"}),
    "report.bulk_export": frozenset({"superadmin", "finance", "auditor"}),
    "crypto.auto_credit.enable": frozenset({"superadmin", "finance"}),
}
DUAL_APPROVAL_ACTIONS: Final = frozenset(ACTION_ROLES)


class AdminAuthorizationError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _bounded(value: int | str, *, name: str, maximum: int) -> str:
    normalized = str(value)
    if not normalized or len(normalized) > maximum:
        raise AdminAuthorizationError(f"Invalid {name}.")
    return normalized


def payload_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


async def effective_roles(session: AsyncSession, telegram_id: int | str) -> frozenset[str]:
    actor = _bounded(telegram_id, name="actor", maximum=20)
    roles: set[str] = set()
    if actor in settings.admin_ids:
        roles.add("superadmin")
    rows = await session.execute(
        select(AdminRoleGrant.role)
        .join(AdminIdentity, AdminIdentity.id == AdminRoleGrant.admin_identity_id)
        .where(
            AdminIdentity.telegram_id == actor,
            AdminIdentity.is_active.is_(True),
            AdminRoleGrant.revoked_at.is_(None),
        )
    )
    roles.update(rows.scalars().all())
    return frozenset(roles & ADMIN_ROLES)


async def require_action_role(session: AsyncSession, telegram_id: int | str, action: str) -> frozenset[str]:
    allowed = ACTION_ROLES.get(action)
    if allowed is None:
        raise AdminAuthorizationError("Unknown privileged action.")
    roles = await effective_roles(session, telegram_id)
    if roles.isdisjoint(allowed):
        raise AdminAuthorizationError("Admin role rejected.")
    return roles


async def issue_action_nonce(
    session: AsyncSession,
    *,
    actor_telegram_id: int | str,
    chat_id: int | str,
    action: str,
    target_type: str,
    target_id: int | str,
    ttl_seconds: int = 180,
) -> str:
    if action not in ACTION_ROLES:
        raise AdminAuthorizationError("Unknown privileged action.")
    if not 30 <= ttl_seconds <= 300:
        raise AdminAuthorizationError("Invalid nonce lifetime.")
    raw = secrets.token_urlsafe(24)
    session.add(
        AdminActionNonce(
            nonce_hash=payload_digest(raw.encode("ascii")),
            actor_telegram_id=_bounded(actor_telegram_id, name="actor", maximum=20),
            chat_id=_bounded(chat_id, name="chat", maximum=24),
            action=action,
            target_type=_bounded(target_type, name="target type", maximum=50),
            target_id=_bounded(target_id, name="target", maximum=180),
            expires_at=_utcnow() + timedelta(seconds=ttl_seconds),
        )
    )
    await session.flush()
    return raw


async def consume_action_nonce(
    session: AsyncSession,
    *,
    nonce: str,
    actor_telegram_id: int | str,
    chat_id: int | str,
    action: str,
    target_type: str,
    target_id: int | str,
) -> None:
    now = _utcnow()
    result = await session.execute(
        update(AdminActionNonce)
        .where(
            AdminActionNonce.nonce_hash == payload_digest(nonce.encode("utf-8")),
            AdminActionNonce.actor_telegram_id == _bounded(actor_telegram_id, name="actor", maximum=20),
            AdminActionNonce.chat_id == _bounded(chat_id, name="chat", maximum=24),
            AdminActionNonce.action == action,
            AdminActionNonce.target_type == _bounded(target_type, name="target type", maximum=50),
            AdminActionNonce.target_id == _bounded(target_id, name="target", maximum=180),
            AdminActionNonce.used_at.is_(None),
            AdminActionNonce.expires_at > now,
        )
        .values(used_at=now)
    )
    if result.rowcount != 1:
        raise AdminAuthorizationError("Action nonce rejected.")


async def create_approval_request(
    session: AsyncSession,
    *,
    actor_telegram_id: int | str,
    action: str,
    target_type: str,
    target_id: int | str,
    payload: bytes,
    ttl_seconds: int = 900,
) -> AdminApprovalRequest:
    if action not in DUAL_APPROVAL_ACTIONS:
        raise AdminAuthorizationError("Action does not support dual approval.")
    if not 60 <= ttl_seconds <= 3600:
        raise AdminAuthorizationError("Invalid approval lifetime.")
    actor = _bounded(actor_telegram_id, name="actor", maximum=20)
    await require_action_role(session, actor, action)
    request = AdminApprovalRequest(
        action=action,
        target_type=_bounded(target_type, name="target type", maximum=50),
        target_id=_bounded(target_id, name="target", maximum=180),
        payload_hash=payload_digest(payload),
        requested_by_telegram_id=actor,
        required_approvals=2,
        status="pending",
        expires_at=_utcnow() + timedelta(seconds=ttl_seconds),
    )
    session.add(request)
    await session.flush()
    return request


async def approve_request(
    session: AsyncSession,
    *,
    approval_request_id: int,
    actor_telegram_id: int | str,
    payload: bytes,
) -> bool:
    actor = _bounded(actor_telegram_id, name="actor", maximum=20)
    request = await session.scalar(
        select(AdminApprovalRequest)
        .where(AdminApprovalRequest.id == approval_request_id)
        .with_for_update()
    )
    if request is None or request.status != "pending" or request.expires_at <= _utcnow():
        raise AdminAuthorizationError("Approval request rejected.")
    if request.requested_by_telegram_id == actor:
        raise AdminAuthorizationError("Second administrator required.")
    if not hmac.compare_digest(request.payload_hash, payload_digest(payload)):
        raise AdminAuthorizationError("Approval payload changed.")
    await require_action_role(session, actor, request.action)
    session.add(AdminApprovalVote(approval_request_id=request.id, actor_telegram_id=actor))
    try:
        await session.flush()
    except IntegrityError as exc:
        raise AdminAuthorizationError("Duplicate approval rejected.") from exc
    vote_count = await session.scalar(
        select(func.count(AdminApprovalVote.id)).where(AdminApprovalVote.approval_request_id == request.id)
    )
    if int(vote_count or 0) + 1 >= request.required_approvals:
        request.status = "approved"
        return True
    return False


async def consume_approved_request(
    session: AsyncSession,
    *,
    approval_request_id: int,
    action: str,
    target_type: str,
    target_id: int | str,
    payload: bytes,
) -> None:
    now = _utcnow()
    result = await session.execute(
        update(AdminApprovalRequest)
        .where(
            AdminApprovalRequest.id == approval_request_id,
            AdminApprovalRequest.status == "approved",
            AdminApprovalRequest.action == action,
            AdminApprovalRequest.target_type == _bounded(target_type, name="target type", maximum=50),
            AdminApprovalRequest.target_id == _bounded(target_id, name="target", maximum=180),
            AdminApprovalRequest.payload_hash == payload_digest(payload),
            AdminApprovalRequest.expires_at > now,
        )
        .values(status="executed", executed_at=now, updated_at=now)
    )
    if result.rowcount != 1:
        raise AdminAuthorizationError("Approved action rejected.")
