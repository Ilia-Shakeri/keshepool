from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import validate_telegram_data
from app.models import Order, User
from app.services.cache_service import check_rate_limit, invalidate_catalog_cache
from app.services.catalog_service import get_public_catalog
from app.services.inventory_service import fulfill_wallet_order
from app.services.user_service import ensure_user_from_telegram_init

router = APIRouter(prefix="/api", tags=["catalog"])

async def current_user(
    telegram_data: Dict[str, Any] = Depends(validate_telegram_data),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await ensure_user_from_telegram_init(db, telegram_data)

class CheckoutRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=120)
    variant_id: str = Field(min_length=1, max_length=120)
    idempotency_key: str | None = Field(
        default=None,
        alias="idempotencyKey",
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )

class ProductVariantResponse(BaseModel):
    id: str
    duration: str
    priceLabel: str
    rawPrice: float
    stockCount: int

class ProductResponse(BaseModel):
    id: str
    title: str
    brand: str
    subtitle: str
    icon: str
    assetUrl: str | None
    gradient: str
    category: str
    features: List[str] | None
    variants: List[ProductVariantResponse]

@router.get("/products", response_model=List[ProductResponse])
async def get_all_products(
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rate_limit = await check_rate_limit(
        "catalog",
        f"user:{user.telegram_id}",
        limit=60,
        window_seconds=60,
    )
    if not rate_limit.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")
    return await get_public_catalog(db)

@router.post("/checkout")
async def checkout_with_wallet(
    payload: CheckoutRequest,
    idempotency_header: str | None = Header(
        default=None,
        alias="X-Idempotency-Key",
        min_length=8,
        max_length=64,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rate_limit = await check_rate_limit(
        "checkout",
        f"user:{user.telegram_id}",
        limit=20,
        window_seconds=60,
    )
    if not rate_limit.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    if (
        idempotency_header
        and payload.idempotency_key
        and idempotency_header != payload.idempotency_key
    ):
        raise HTTPException(
            status_code=409,
            detail="Idempotency key header and body do not match.",
        )

    order = await fulfill_wallet_order(
        db=db,
        user=user,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
        idempotency_key=idempotency_header or payload.idempotency_key,
    )

    await invalidate_catalog_cache()

    order_result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.product),
            selectinload(Order.variant),
            selectinload(Order.inventory_item),
        )
        .where(Order.id == order.id)
    )
    hydrated_order = order_result.scalars().first()

    return {
        "status": "success",
        "order": {
            "id": hydrated_order.public_id,
            "productTitle": hydrated_order.product.title,
            "productBrand": hydrated_order.product.brand,
            "variantDuration": hydrated_order.variant.duration,
            "credentials": hydrated_order.inventory_item.credentials,
            "createdAt": hydrated_order.created_at.isoformat(),
            "totalAmount": float(hydrated_order.total_amount),
        },
    }
