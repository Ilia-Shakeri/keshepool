import re
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import settings
from app.core.security import validate_fresh_telegram_data, validate_telegram_data
from app.models import (
    CredentialRevealEvent,
    Notification,
    Order,
    OrderStatus,
    Transaction,
    User,
    Wallet,
)
from app.services.admin_audit_service import add_admin_audit
from app.services.cache_service import check_rate_limit
from app.services.catalog_service import MAX_CREDENTIAL_LENGTH
from app.services.credential_access_service import (
    MASKED_CREDENTIAL_PREVIEW,
    credential_is_revealable,
)
from app.services.http_response_security import apply_no_store_headers, no_store_response_headers
from app.services.order_pagination_service import (
    ORDER_NEXT_CURSOR_HEADER,
    ORDER_PAGE_DEFAULT_LIMIT,
    ORDER_PAGE_MAX_LIMIT,
    InvalidOrderCursor,
    build_user_order_page_statement,
    decode_order_cursor,
    encode_order_cursor,
)
from app.services.user_service import ensure_user_from_telegram_init, normalize_referral_code

router = APIRouter(prefix="/api", tags=["users"])


class BootstrapRequest(BaseModel):
    referrerTelegramId: Optional[str] = Field(default=None, max_length=64)


class CredentialRevealResponse(BaseModel):
    orderId: str = Field(min_length=1, max_length=120)
    credential: str = Field(min_length=1, max_length=MAX_CREDENTIAL_LENGTH)


class UserOrderResponse(BaseModel):
    id: str
    title: str
    brand: str
    duration: str
    status: str
    createdAt: str
    expiresAt: str | None
    credentialPreview: str | None
    credentialAvailable: bool
    assetUrl: str | None
    icon: str
    gradient: str
    totalAmount: float


class NotificationMarkReadThroughRequest(BaseModel):
    throughId: int = Field(gt=0, le=2_147_483_647)


_PUBLIC_ORDER_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$"


def _credential_available_for_order(order: Order) -> bool:
    reveal_count = getattr(order, "credential_reveal_count", 0) or 0
    return bool(
        reveal_count < settings.CREDENTIAL_REVEAL_MAX_PER_ORDER
        and credential_is_revealable(order)
    )


def _request_id(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    return str(value)[:64] if value is not None else None


def _credential_reveal_error(status_code: int, detail: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=detail,
        headers=no_store_response_headers(),
    )


async def _enforce_notification_write_rate(user: User) -> None:
    decision = await check_rate_limit(
        "notification-read",
        f"user:{user.telegram_id}",
        limit=30,
        window_seconds=60,
    )
    if not decision.backend_available:
        raise HTTPException(status_code=503, detail="Notification write protection is unavailable.")
    if not decision.allowed:
        raise HTTPException(status_code=429, detail="Too many notification write requests.")


async def _record_credential_reveal_attempt(
    db: AsyncSession,
    *,
    request: Request,
    user: User,
    public_id: str,
    order: Order | None,
    outcome: str,
    reveal_count: int | None,
) -> None:
    request_id = _request_id(request)
    db.add(
        CredentialRevealEvent(
            order_id=order.id if order is not None else None,
            user_id=user.id,
            actor_telegram_id=str(user.telegram_id)[:20],
            order_public_id=public_id,
            outcome=outcome,
            reveal_count=reveal_count,
            request_id=request_id,
        )
    )
    order_status = order.status.value if order is not None else None
    await add_admin_audit(
        db,
        actor_telegram_id=user.telegram_id,
        action="credential.reveal",
        target_type="order",
        target_id=public_id,
        request_id=request_id,
        outcome="success" if outcome == "allowed" else "rejected",
        reason=None if outcome == "allowed" else outcome,
        details={
            "order_status": order_status,
            "reveal_count": reveal_count,
        },
    )


def signed_referral_code(telegram_data: Dict[str, Any]) -> Optional[str]:
    start_param = telegram_data.get("start_param")
    if not isinstance(start_param, str) or not re.fullmatch(r"ref_[0-9a-f]{32}", start_param):
        return None
    return normalize_referral_code(start_param.removeprefix("ref_"))


async def current_user(
    telegram_data: Dict[str, Any] = Depends(validate_telegram_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await ensure_user_from_telegram_init(db, telegram_data)


async def current_fresh_user(
    telegram_data: Dict[str, Any] = Depends(validate_fresh_telegram_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await ensure_user_from_telegram_init(db, telegram_data)


@router.post("/me/bootstrap")
async def bootstrap_user(
    _payload: BootstrapRequest,
    telegram_data: Dict[str, Any] = Depends(validate_telegram_data),
    db: AsyncSession = Depends(get_db),
):
    user = await ensure_user_from_telegram_init(
        db=db,
        telegram_data=telegram_data,
        referral_code=signed_referral_code(telegram_data),
    )
    return await get_profile_payload(user, db)


@router.get("/me")
async def get_me(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await get_profile_payload(user, db)


async def get_profile_payload(user: User, db: AsyncSession):
    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()

    order_count_result = await db.execute(select(func.count(Order.id)).where(Order.user_id == user.id))
    order_count = order_count_result.scalar_one()

    active_order_count_result = await db.execute(
        select(func.count(Order.id)).where(Order.user_id == user.id, Order.status == OrderStatus.ACTIVE)
    )
    active_order_count = active_order_count_result.scalar_one()

    return {
        "user": {
            "id": user.id,
            "telegramId": user.telegram_id,
            "username": user.username,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "photoUrl": user.photo_url,
            "role": user.role,
            "referralCode": user.referral_code,
        },
        "walletBalance": float(wallet.balance) if wallet else 0,
        "orderCount": int(order_count),
        "activeOrderCount": int(active_order_count),
    }


@router.get("/wallet/balance")
async def get_wallet_balance(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    return {"balance": float(wallet.balance) if wallet else 0}


@router.get("/wallet/transactions")
async def get_wallet_transactions(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    if not wallet:
        return []

    tx_result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.card_transfer_receipt))
        .where(Transaction.wallet_id == wallet.id)
        .order_by(Transaction.created_at.desc())
        .limit(30)
    )
    transactions = tx_result.scalars().all()
    return [
        {
            "id": tx.id,
            "amount": float(tx.amount),
            "type": tx.type.value,
            "status": tx.status.value,
            "currency": tx.currency,
            "gateway": tx.gateway,
            "referenceId": tx.reference_id,
            "description": tx.description,
            "hasReceipt": tx.card_transfer_receipt is not None,
            "createdAt": tx.created_at.isoformat(),
        }
        for tx in transactions
    ]


@router.get("/orders", response_model=list[UserOrderResponse])
async def get_orders(
    response: Response,
    cursor: Annotated[str | None, Query(min_length=22, max_length=22)] = None,
    limit: Annotated[int, Query(ge=1, le=ORDER_PAGE_MAX_LIMIT)] = ORDER_PAGE_DEFAULT_LIMIT,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    apply_no_store_headers(response)
    decoded_cursor = None
    if cursor is not None:
        try:
            decoded_cursor = decode_order_cursor(cursor)
        except InvalidOrderCursor as exc:
            raise HTTPException(status_code=422, detail="Invalid order cursor.") from exc

    result = await db.execute(
        build_user_order_page_statement(
            user_id=user.id,
            limit=limit,
            cursor=decoded_cursor,
        )
    )
    rows = result.scalars().all()
    has_next_page = len(rows) > limit
    orders = rows[:limit]
    if has_next_page:
        last_order = orders[-1]
        response.headers[ORDER_NEXT_CURSOR_HEADER] = encode_order_cursor(
            last_order.created_at,
            last_order.id,
        )
    return [
        {
            "id": order.public_id,
            "title": order.product.title,
            "brand": order.product.brand,
            "duration": order.variant.duration,
            "status": order.status.value,
            "createdAt": order.created_at.isoformat(),
            "expiresAt": order.expires_at.isoformat() if order.expires_at else None,
            "credentialPreview": (
                MASKED_CREDENTIAL_PREVIEW if _credential_available_for_order(order) else None
            ),
            "credentialAvailable": _credential_available_for_order(order),
            "assetUrl": order.product.asset_url,
            "icon": order.product.icon,
            "gradient": order.product.gradient,
            "totalAmount": float(order.total_amount),
        }
        for order in orders
    ]


@router.post(
    "/orders/{public_id}/reveal-credential",
    response_model=CredentialRevealResponse,
)
async def reveal_order_credential(
    request: Request,
    response: Response,
    public_id: str = Path(
        min_length=1,
        max_length=120,
        pattern=_PUBLIC_ORDER_ID_PATTERN,
    ),
    user: User = Depends(current_fresh_user),
    db: AsyncSession = Depends(get_db),
) -> CredentialRevealResponse:
    apply_no_store_headers(response)
    rate_limit = await check_rate_limit(
        "credential-reveal",
        f"user:{user.telegram_id}",
        limit=10,
        window_seconds=60,
    )
    if not rate_limit.backend_available:
        raise _credential_reveal_error(
            status_code=503,
            detail="Credential reveal protection is unavailable.",
        )
    if not rate_limit.allowed:
        raise _credential_reveal_error(
            status_code=429,
            detail="Too many credential reveal requests.",
        )

    result = await db.execute(
        select(Order)
        .options(selectinload(Order.inventory_item))
        .where(
            Order.public_id == public_id,
            Order.user_id == user.id,
        )
        .with_for_update(of=Order)
    )
    order = result.scalars().first()
    if order is None:
        await _record_credential_reveal_attempt(
            db,
            request=request,
            user=user,
            public_id=public_id,
            order=None,
            outcome="denied_not_found",
            reveal_count=None,
        )
        await db.commit()
        raise _credential_reveal_error(status_code=404, detail="Order not found.")

    reveal_count = getattr(order, "credential_reveal_count", 0) or 0
    if reveal_count >= settings.CREDENTIAL_REVEAL_MAX_PER_ORDER:
        await _record_credential_reveal_attempt(
            db,
            request=request,
            user=user,
            public_id=public_id,
            order=order,
            outcome="denied_limit",
            reveal_count=reveal_count,
        )
        await db.commit()
        raise _credential_reveal_error(
            status_code=409,
            detail="Credential reveal limit reached for this order.",
        )
    if not credential_is_revealable(order):
        await _record_credential_reveal_attempt(
            db,
            request=request,
            user=user,
            public_id=public_id,
            order=order,
            outcome="denied_state",
            reveal_count=reveal_count,
        )
        await db.commit()
        raise _credential_reveal_error(
            status_code=409,
            detail="Credential is unavailable for this order state.",
        )

    credential = order.inventory_item.credentials
    if len(credential) > MAX_CREDENTIAL_LENGTH:
        await _record_credential_reveal_attempt(
            db,
            request=request,
            user=user,
            public_id=public_id,
            order=order,
            outcome="denied_size",
            reveal_count=reveal_count,
        )
        await db.commit()
        raise _credential_reveal_error(
            status_code=409,
            detail="Credential exceeds the reveal response limit.",
        )

    order.credential_reveal_count = reveal_count + 1
    await _record_credential_reveal_attempt(
        db,
        request=request,
        user=user,
        public_id=public_id,
        order=order,
        outcome="allowed",
        reveal_count=order.credential_reveal_count,
    )
    await db.commit()
    return CredentialRevealResponse(orderId=order.public_id, credential=credential)


@router.get("/notifications")
async def get_notifications(
    response: Response,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    apply_no_store_headers(response)
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(20)
    )
    notifications = result.scalars().all()
    return [
        {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "isRead": item.is_read,
            "createdAt": item.created_at.isoformat(),
        }
        for item in notifications
    ]


@router.post("/notifications/mark-read")
async def mark_notifications_read(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await _enforce_notification_write_rate(user)
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
        .returning(Notification.id)
    )
    marked = len(result.fetchall())
    await db.commit()
    return {"marked": marked}


@router.post("/notifications/{notification_id}/mark-read")
async def mark_notification_read(
    notification_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _enforce_notification_write_rate(user)
    result = await db.execute(
        update(Notification)
        .where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
        .returning(Notification.id)
    )
    marked = len(result.fetchall())
    if marked:
        await db.commit()
        return {"marked": 1, "notificationId": notification_id}

    owned_result = await db.execute(
        select(Notification.id).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    if owned_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    return {"marked": 0, "notificationId": notification_id}


@router.post("/notifications/mark-read-through")
async def mark_notifications_read_through(
    payload: NotificationMarkReadThroughRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await _enforce_notification_write_rate(user)
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.id <= payload.throughId,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
        .returning(Notification.id)
    )
    marked = len(result.fetchall())
    await db.commit()
    return {"marked": marked, "throughId": payload.throughId}
