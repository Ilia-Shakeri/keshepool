from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import redis_client
from app.models import InventoryItem, ItemStatus, Product, ProductVariant, Order, OrderStatus, Wallet

router = APIRouter(prefix="/api/admin", tags=["admin"])
api_key_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)

class VariantSchema(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    duration: str = Field(min_length=1, max_length=120)
    priceLabel: str = Field(min_length=1, max_length=50)
    rawPrice: float = Field(gt=0)

class ProductSchema(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=180)
    brand: str = Field(min_length=1, max_length=180)
    subtitle: str = ""
    icon: str = "Box"
    assetUrl: str | None = None
    gradient: str = "from-gray-700 to-black"
    category: str = "tools"
    variants: List[VariantSchema]

class ConfigUploadSchema(BaseModel):
    product_id: str
    variant_id: str
    credentials: List[str]

class ProductUpdateSchema(BaseModel):
    title: Optional[str] = None
    rawPrice: Optional[float] = None
    assetUrl: Optional[str] = None

async def verify_system_admin(request: Request):
    api_key = request.headers.get("X-Admin-Token")
    if not api_key or api_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal API key.")
    return True

@router.get("/stats")
async def get_system_stats(
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db)
):
    revenue_result = await db.execute(
        select(func.sum(Order.total_amount)).where(Order.status == OrderStatus.ACTIVE)
    )
    revenue = revenue_result.scalar() or 0

    return {
        "revenue": float(revenue),
        "status": "operational"
    }

@router.get("/products")
async def list_internal_products(
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Product).options(selectinload(Product.variants)).order_by(Product.brand.asc())
    )
    products = result.scalars().all()
    
    output = []
    for product in products:
        stock_result = await db.execute(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.product_id == product.id,
                InventoryItem.status == ItemStatus.AVAILABLE
            )
        )
        stock_count = stock_result.scalar() or 0
        output.append({
            "id": product.id,
            "brand": product.brand,
            "is_active": product.is_active,
            "available_stock": stock_count,
            "variants": [{"id": v.id, "raw_price": float(v.raw_price)} for v in product.variants if v.is_active]
        })
    return output

@router.patch("/products/{product_id}")
async def patch_product_internals(
    product_id: str,
    payload: ProductUpdateSchema,
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db)
):
    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalars().first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    if payload.title:
        product.title = payload.title
        product.brand = payload.title
    
    if payload.assetUrl:
        product.asset_url = payload.assetUrl
        product.icon = "Image"
        
    if payload.rawPrice is not None:
        variants_result = await db.execute(
            select(ProductVariant)
            .where(ProductVariant.product_id == product_id, ProductVariant.is_active.is_(True))
            .with_for_update()
        )
        for variant in variants_result.scalars().all():
            variant.raw_price = payload.rawPrice
            variant.price_label = f"{int(payload.rawPrice):,}"
            
    await db.commit()
    await redis_client.delete("cache:products:all")
    return {"status": "success"}

@router.post("/products")
async def create_or_update_product(
    payload: ProductSchema,
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Product).where(Product.id == payload.id))
    product = result.scalars().first()

    if not product:
        product = Product(id=payload.id)
        db.add(product)

    product.title = payload.title
    product.brand = payload.brand
    product.subtitle = payload.subtitle
    product.icon = payload.icon or "Box"
    product.asset_url = payload.assetUrl
    product.gradient = payload.gradient
    product.category = payload.category
    product.is_active = True

    existing_variants_result = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id == payload.id).with_for_update()
    )
    existing_variants = {variant.id: variant for variant in existing_variants_result.scalars().all()}
    incoming_variant_ids = set()

    for variant_payload in payload.variants:
        incoming_variant_ids.add(variant_payload.id)
        variant = existing_variants.get(variant_payload.id)
        if not variant:
            variant = ProductVariant(id=variant_payload.id, product_id=payload.id)
            db.add(variant)
        variant.duration = variant_payload.duration
        variant.price_label = variant_payload.priceLabel
        variant.raw_price = variant_payload.rawPrice
        variant.is_active = True

    for variant_id, variant in existing_variants.items():
        if variant_id not in incoming_variant_ids:
            variant.is_active = False

    await db.commit()
    await redis_client.delete("cache:products:all")
    return {"status": "success"}

@router.post("/inventory/bulk-upload")
async def bulk_upload_inventory(
    payload: ConfigUploadSchema,
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db),
):
    variant_result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.id == payload.variant_id,
            ProductVariant.product_id == payload.product_id,
        )
    )
    if not variant_result.scalars().first():
        raise HTTPException(status_code=404, detail="Product variant not found.")

    inserted_count = 0
    for raw_credential in payload.credentials:
        credential = raw_credential.strip()
        if not credential:
            continue
            
        exists_result = await db.execute(
            select(InventoryItem).where(
                InventoryItem.product_id == payload.product_id,
                InventoryItem.variant_id == payload.variant_id,
                InventoryItem.credentials == credential,
            ).with_for_update()
        )
        
        if exists_result.scalars().first():
            continue
            
        db.add(
            InventoryItem(
                product_id=payload.product_id,
                variant_id=payload.variant_id,
                credentials=credential,
                status=ItemStatus.AVAILABLE,
            )
        )
        inserted_count += 1

    await db.commit()
    await redis_client.delete("cache:products:all")
    return {"status": "success", "insertedCount": inserted_count}