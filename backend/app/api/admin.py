import secrets
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import InventoryItem, ItemStatus, Order, OrderStatus, Product, utcnow
from app.services.admin_audit_service import add_admin_audit
from app.services.catalog_service import (
    CatalogMutationError,
    VariantOwnershipError,
    bulk_insert_stock,
    catalog_diagnostics,
    commit_catalog_change,
    patch_product,
    upsert_product,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

class VariantSchema(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=120)
    duration: str = Field(min_length=1, max_length=120)
    priceLabel: str = Field(min_length=1, max_length=50)
    rawPrice: float = Field(gt=0, le=999999999999.99)
    isActive: bool = True

class ProductSchema(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=180)
    brand: str = Field(min_length=1, max_length=180)
    subtitle: str = Field(default="", max_length=500)
    icon: str = "Box"
    assetUrl: str | None = Field(default=None, max_length=2048)
    gradient: str = "from-gray-700 to-black"
    category: str = "tools"
    features: List[str] | None = Field(default=None, max_length=4)
    isActive: bool = True
    variants: List[VariantSchema] = Field(min_length=1, max_length=50)

class ConfigUploadSchema(BaseModel):
    product_id: str = Field(min_length=1, max_length=120)
    variant_id: str = Field(min_length=1, max_length=120)
    credentials: List[str] = Field(min_length=1, max_length=5000)

class ProductUpdateSchema(BaseModel):
    title: Optional[str] = None
    brand: Optional[str] = None
    subtitle: Optional[str] = None
    rawPrice: Optional[float] = Field(default=None, gt=0, le=999999999999.99)
    variantId: Optional[str] = None
    assetUrl: Optional[str] = None
    features: List[str] | None = None
    isActive: Optional[bool] = None

async def verify_system_admin(request: Request):
    api_key = request.headers.get("X-Admin-Token")
    if not api_key or not secrets.compare_digest(api_key, settings.ADMIN_API_KEY):
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
    stock_result = await db.execute(
        select(InventoryItem.product_id, func.count(InventoryItem.id))
        .where(
            InventoryItem.status == ItemStatus.AVAILABLE,
            or_(
                InventoryItem.expires_at.is_(None),
                InventoryItem.expires_at > utcnow(),
            ),
        )
        .group_by(InventoryItem.product_id)
    )
    stock_by_product = dict(stock_result.all())

    output = []
    for product in products:
        output.append({
            "id": product.id,
            "brand": product.brand,
            "is_active": product.is_active,
            "available_stock": int(stock_by_product.get(product.id, 0)),
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
    values = {}
    if payload.title is not None:
        values["title"] = payload.title
    if payload.brand is not None:
        values["brand"] = payload.brand
    if payload.subtitle is not None:
        values["subtitle"] = payload.subtitle
    if payload.assetUrl is not None:
        values["asset_url"] = payload.assetUrl
        values["icon"] = "Image"
    if "features" in payload.model_fields_set:
        values["features"] = payload.features

    try:
        result = await patch_product(
            db,
            product_id,
            values=values,
            active=payload.isActive,
            raw_price=Decimal(str(payload.rawPrice)) if payload.rawPrice is not None else None,
            variant_id=payload.variantId,
            commit=False,
        )
        await add_admin_audit(
            db,
            actor_telegram_id="internal-api",
            action="catalog.product.update",
            target_type="product",
            target_id=product_id,
            details={"fields": sorted(values), "active_changed": payload.isActive is not None},
        )
        result.cache_invalidated = await commit_catalog_change(db)
    except CatalogMutationError as exc:
        status_code = 404 if str(exc) in {"Product not found.", "Product variant not found."} else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return {"status": "success", "result": result.to_dict()}

@router.post("/products")
async def create_or_update_product(
    payload: ProductSchema,
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await upsert_product(
            db,
            payload.model_dump(),
            replace_variants=True,
            commit=False,
        )
        await add_admin_audit(
            db,
            actor_telegram_id="internal-api",
            action="catalog.product.upsert",
            target_type="product",
            target_id=payload.id,
            details={"variant_count": len(payload.variants)},
        )
        result.cache_invalidated = await commit_catalog_change(db)
    except VariantOwnershipError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CatalogMutationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"status": "success", "result": result.to_dict()}

@router.post("/inventory/bulk-upload")
async def bulk_upload_inventory(
    payload: ConfigUploadSchema,
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await bulk_insert_stock(
            db,
            product_id=payload.product_id,
            variant_id=payload.variant_id,
            credentials=payload.credentials,
            commit=False,
        )
        await add_admin_audit(
            db,
            actor_telegram_id="internal-api",
            action="catalog.stock.import",
            target_type="variant",
            target_id=payload.variant_id,
            details={
                "product_id": payload.product_id,
                "inserted_count": result.inserted_stock_count,
                "duplicate_count": result.duplicate_stock_count,
            },
        )
        result.cache_invalidated = await commit_catalog_change(db)
    except CatalogMutationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "status": "success",
        "insertedCount": result.inserted_stock_count,
        "duplicateCount": result.duplicate_stock_count,
    }


@router.get("/products/{product_id}/diagnostics")
async def get_catalog_diagnostics(
    product_id: str,
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db),
):
    return await catalog_diagnostics(db, product_id)


@router.post("/catalog/refresh")
async def refresh_catalog_cache(
    _: bool = Depends(verify_system_admin),
    db: AsyncSession = Depends(get_db),
):
    await add_admin_audit(
        db,
        actor_telegram_id="internal-api",
        action="catalog.cache.refresh",
        target_type="catalog",
    )
    cache_invalidated = await commit_catalog_change(db)
    return {"status": "success", "cacheInvalidated": cache_invalidated}
