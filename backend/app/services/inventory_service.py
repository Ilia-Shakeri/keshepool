import secrets
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
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
    TransactionType,
    User,
    Wallet,
    utcnow,
)


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def fulfill_wallet_order(
    db: AsyncSession,
    user: User,
    product_id: str,
    variant_id: str,
) -> Order:
    try:
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

        wallet_result = await db.execute(
            select(Wallet).where(Wallet.user_id == user.id).with_for_update()
        )
        wallet = wallet_result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found.")

        price = _money(variant.raw_price)
        if wallet.balance < price:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance.")

        item_result = await db.execute(
            select(InventoryItem)
            .where(
                InventoryItem.product_id == product_id,
                InventoryItem.variant_id == variant_id,
                InventoryItem.status == ItemStatus.AVAILABLE,
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        item = item_result.scalars().first()
        if not item:
            raise HTTPException(status_code=409, detail="This product is currently out of stock.")

        wallet.balance = _money(wallet.balance) - price
        item.status = ItemStatus.ASSIGNED
        item.assigned_to_user_id = user.id
        item.assigned_at = utcnow()

        public_id = f"KP-{secrets.token_hex(4).upper()}"
        order = Order(
            public_id=public_id,
            user_id=user.id,
            product_id=product_id,
            variant_id=variant_id,
            inventory_item_id=item.id,
            total_amount=price,
            status=OrderStatus.ACTIVE,
        )
        db.add(order)
        db.add(
            Transaction(
                wallet_id=wallet.id,
                amount=-price,
                type=TransactionType.PURCHASE,
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