import secrets
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

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
from app.services.catalog_service import canonical_price_label
from app.core.money import quantized_decimal


_WALLET_LIMIT = Decimal("9999999999999999.99")


def _money(value) -> Decimal:
    return quantized_decimal(
        value,
        Decimal("0.01"),
        minimum=-_WALLET_LIMIT,
        maximum=_WALLET_LIMIT,
    )


def _snapshot_text(value: object, *, max_length: int) -> str:
    text_value = str(value or "").strip()
    if not text_value or len(text_value) > max_length:
        raise HTTPException(status_code=409, detail="Product data is not ready for sale.")
    return text_value


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

        # Lock order is wallet, catalog rows, then inventory.
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

        variant_result = await db.execute(
            select(ProductVariant)
            .join(Product, Product.id == ProductVariant.product_id)
            .options(contains_eager(ProductVariant.product))
            .where(
                ProductVariant.id == variant_id,
                ProductVariant.product_id == product_id,
                ProductVariant.is_active.is_(True),
                Product.is_active.is_(True),
            )
            .with_for_update(read=True, of=(ProductVariant, Product))
        )
        variant = variant_result.scalars().first()
        if not variant or not variant.product:
            raise HTTPException(status_code=404, detail="Product variant not found.")

        price = _money(variant.raw_price)
        if price <= 0:
            raise HTTPException(status_code=409, detail="Product price is not valid.")
        if wallet.balance < price:
            raise HTTPException(status_code=400, detail="Insufficient wallet balance.")

        product_title_snapshot = _snapshot_text(variant.product.title, max_length=180)
        product_brand_snapshot = _snapshot_text(variant.product.brand, max_length=180)
        variant_duration_snapshot = _snapshot_text(variant.duration, max_length=120)
        variant_price_label_snapshot = canonical_price_label(price)

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
            .order_by(
                InventoryItem.expires_at.asc().nulls_last(),
                InventoryItem.created_at.asc(),
                InventoryItem.id.asc(),
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
            product_title_snapshot=product_title_snapshot,
            product_brand_snapshot=product_brand_snapshot,
            variant_duration_snapshot=variant_duration_snapshot,
            variant_price_label_snapshot=variant_price_label_snapshot,
            currency_snapshot="IRR",
            unit_price_amount=price,
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            total_amount_snapshot=price,
            snapshot_state="complete",
            snapshot_quarantine_reason=None,
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
                description=f"Purchase: {product_brand_snapshot} {variant_duration_snapshot}",
            )
        )
        
        db.add(
            Notification(
                user_id=user.id,
                title="سفارش جدید",
                description=f"سفارش {product_brand_snapshot} با موفقیت فعال شد.",
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
