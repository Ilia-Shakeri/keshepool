import secrets
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    InventoryItem,
    ItemStatus,
    Notification,
    Order,
    OrderStatus,
    Product,
    ProductVariant,
    Transaction,
    TransactionStatus,
    TransactionType,
    User,
    Wallet,
    utcnow,
)


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def _existing_idempotent_order(
    db: AsyncSession,
    user_id: int,
    idempotency_key: str | None,
    product_id: str,
    variant_id: str,
) -> Order | None:
    if not idempotency_key:
        return None

    result = await db.execute(
        select(Order).where(
            Order.user_id == user_id,
            Order.idempotency_key == idempotency_key,
        )
    )
    order = result.scalars().first()
    if order and (order.product_id != product_id or order.variant_id != variant_id):
        raise HTTPException(
            status_code=409,
            detail="This idempotency key was already used for another product.",
        )
    return order


async def _new_public_id(db: AsyncSession) -> str:
    for _ in range(5):
        public_id = f"KP-{secrets.token_hex(16).upper()}"
        result = await db.execute(select(Order.id).where(Order.public_id == public_id))
        if result.scalar_one_or_none() is None:
            return public_id
    raise HTTPException(status_code=503, detail="Could not allocate a unique order ID.")


async def fulfill_wallet_order(
    db: AsyncSession,
    user: User,
    product_id: str,
    variant_id: str,
    idempotency_key: str | None = None,
) -> Order:
    try:
        existing_order = await _existing_idempotent_order(
            db, user.id, idempotency_key, product_id, variant_id
        )
        if existing_order:
            return existing_order

        # Validate the requested product variant
        variant_result = await db.execute(
            select(ProductVariant)
            .options(selectinload(ProductVariant.product))
            .where(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product_id,
                ProductVariant.is_active.is_(True),
            )
        )
        variant = variant_result.scalars().first()
        if not variant or not variant.product or not variant.product.is_active:
            raise HTTPException(status_code=404, detail="Product variant not found.")

        # DETERMINISTIC LOCKING ORDER: 
        # Always acquire the lock on the Wallet BEFORE the InventoryItem. 
        # This prevents transaction deadlocks across concurrent requests.
        wallet_result = await db.execute(
            select(Wallet).where(Wallet.user_id == user.id).with_for_update()
        )
        wallet = wallet_result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found.")

        # Requests from one user serialize on the wallet row. Recheck after the
        # lock so a retry returns the order committed by the first request.
        existing_order = await _existing_idempotent_order(
            db, user.id, idempotency_key, product_id, variant_id
        )
        if existing_order:
            await db.commit()
            return existing_order

        price = _money(variant.raw_price)
        if wallet.balance < price:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance.")

        now = utcnow()
        await db.execute(
            update(InventoryItem)
            .where(
                InventoryItem.product_id == product_id,
                InventoryItem.variant_id == variant_id,
                InventoryItem.status == ItemStatus.AVAILABLE,
                InventoryItem.expires_at.is_not(None),
                InventoryItem.expires_at <= now,
            )
            .values(status=ItemStatus.EXPIRED)
        )

        # Acquire lock on one live item only.
        item_result = await db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.product_id == product_id,
                InventoryItem.variant_id == variant_id,
                InventoryItem.status == ItemStatus.AVAILABLE,
                or_(
                    InventoryItem.expires_at.is_(None),
                    InventoryItem.expires_at > now,
                ),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        item = item_result.scalars().first()
        if not item:
            raise HTTPException(status_code=409, detail="This product is currently out of stock.")

        # Process financial adjustments and assign inventory
        wallet.balance = _money(wallet.balance) - price
        item.status = ItemStatus.ASSIGNED
        item.assigned_to_user_id = user.id
        item.assigned_at = utcnow()

        public_id = await _new_public_id(db)
        order = Order(
            public_id=public_id,
            user_id=user.id,
            product_id=product_id,
            variant_id=variant_id,
            inventory_item_id=item.id,
            total_amount=price,
            idempotency_key=idempotency_key,
            status=OrderStatus.ACTIVE,
        )
        db.add(order)
        
        db.add(
            Transaction(
                wallet_id=wallet.id,
                amount=-price,
                currency="IRR",
                gateway="wallet",
                type=TransactionType.PURCHASE,
                status=TransactionStatus.SUCCESS,
                reference_id=public_id,
                description=f"Purchase: {variant.product.brand} {variant.duration}",
            )
        )
        
        db.add(
            Notification(
                user_id=user.id,
                title="سفارش جدید",
                description=f"سفارش {variant.product.brand} با موفقیت فعال شد.",
            )
        )

        await db.commit()
        await db.refresh(order)
        return order
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Order fulfillment failed.") from exc
