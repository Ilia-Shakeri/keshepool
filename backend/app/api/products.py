import json
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.redis import redis_client
from app.core.security import validate_telegram_data
from app.models import InventoryItem, ItemStatus, Order, Product, User
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

def parse_product_features(raw_features: str | None) -> List[str] | None:
    """Return product feature labels only when the stored JSON is valid."""
    if not raw_features:
        return None

    try:
        parsed = json.loads(raw_features)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, list):
        return None

    features = [str(feature).strip() for feature in parsed if str(feature).strip()]
    return features or None

@router.get("/products", response_model=List[ProductResponse])
async def get_all_products(
    request: Request,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rate_key = f"rate_limit:products:user:{user.telegram_id}"
    
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60, nx=True)
        results = await pipe.execute()
        
    requests = results[0]
    if requests > 60:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    cache_key = "cache:products:all"
    cached_products = await redis_client.get(cache_key)
    
    if cached_products:
        return json.loads(cached_products)

    stock_result = await db.execute(
        select(InventoryItem.variant_id, func.count(InventoryItem.id))
        .where(InventoryItem.status == ItemStatus.AVAILABLE)
        .group_by(InventoryItem.variant_id)
    )
    stock_by_variant = {variant_id: count for variant_id, count in stock_result.all()}

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.variants))
        .where(Product.is_active.is_(True))
        .order_by(Product.created_at.desc())
    )
    products = result.scalars().all()

    output: List[Dict[str, Any]] = []
    for product in products:
        # Only active variants are exposed so the mini-app mirrors admin-bot availability.
        active_variants = [variant for variant in product.variants if variant.is_active]
        if not active_variants:
            continue

        output.append(
            {
                "id": product.id,
                "title": product.title,
                "brand": product.brand,
                "subtitle": product.subtitle or "",
                "icon": product.icon or "Box",
                "assetUrl": product.asset_url,
                "gradient": product.gradient or "from-gray-700 to-black",
                "category": product.category or "tools",
                "features": parse_product_features(product.features),
                "variants": [
                    {
                        "id": variant.id,
                        "duration": variant.duration,
                        "priceLabel": variant.price_label,
                        "rawPrice": float(variant.raw_price),
                        "stockCount": int(stock_by_variant.get(variant.id, 0)),
                    }
                    for variant in active_variants
                ],
            }
        )
        
    await redis_client.setex(cache_key, 60, json.dumps(output, ensure_ascii=False))
    return output

@router.post("/checkout")
async def checkout_with_wallet(
    payload: CheckoutRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # Enforce strict rate limits on order fulfillment initialization
    rate_key = f"rate_limit:checkout:user:{user.telegram_id}"
    
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60, nx=True)
        results = await pipe.execute()
        
    requests = results[0]
    if requests > 60:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    order = await fulfill_wallet_order(
        db=db,
        user=user,
        product_id=payload.product_id,
        variant_id=payload.variant_id,
    )

    await redis_client.delete("cache:products:all")

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
