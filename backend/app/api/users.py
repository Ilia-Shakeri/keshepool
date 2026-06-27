from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import validate_telegram_data
from app.models import Notification, Order, OrderStatus, Transaction, User, Wallet
from app.services.user_service import ensure_user_from_telegram_init

router = APIRouter(prefix="/api", tags=["users"])


class BootstrapRequest(BaseModel):
    referrerTelegramId: Optional[str] = None


async def current_user(
    telegram_data: Dict[str, Any] = Depends(validate_telegram_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await ensure_user_from_telegram_init(db, telegram_data)


@router.post("/me/bootstrap")
async def bootstrap_user(
    payload: BootstrapRequest,
    telegram_data: Dict[str, Any] = Depends(validate_telegram_data),
    db: AsyncSession = Depends(get_db),
):
    user = await ensure_user_from_telegram_init(
        db=db,
        telegram_data=telegram_data,
        referrer_telegram_id=payload.referrerTelegramId,
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

    from app.models import Transaction
    tx_result = await db.execute(
        select(Transaction)
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
            "createdAt": tx.created_at.isoformat(),
        }
        for tx in transactions
    ]


@router.get("/orders")
async def get_orders(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.product),
            selectinload(Order.variant),
            selectinload(Order.inventory_item),
        )
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    orders = result.scalars().all()
    return [
        {
            "id": order.public_id,
            "title": order.product.title,
            "brand": order.product.brand,
            "duration": order.variant.duration,
            "status": order.status.value,
            "createdAt": order.created_at.isoformat(),
            "expiresAt": order.expires_at.isoformat() if order.expires_at else None,
            "credentials": order.inventory_item.credentials,
            "assetUrl": order.product.asset_url,
            "icon": order.product.icon,
            "gradient": order.product.gradient,
            "totalAmount": float(order.total_amount),
        }
        for order in orders
    ]


@router.get("/notifications")
async def get_notifications(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
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