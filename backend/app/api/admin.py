import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from app.models import InventoryItem, ItemStatus, User, Product, ProductVariant
from app.core.database import get_db
from app.core.security import validate_telegram_data

router = APIRouter(prefix="/api/admin", tags=["admin"])

class VariantSchema(BaseModel):
    id: str
    duration: str
    priceLabel: str
    rawPrice: float

class ProductSchema(BaseModel):
    id: str
    title: str
    brand: str
    subtitle: str
    icon: str
    gradient: str
    category: str
    variants: List[VariantSchema]

class ConfigUploadSchema(BaseModel):
    product_id: str
    variant_id: str
    credentials: List[str]

async def verify_admin(telegram_data: dict = Depends(validate_telegram_data), db: AsyncSession = Depends(get_db)):
    """
    Enforces RBAC verification against the Telegram InitData payload.
    """
    try:
        user_info = json.loads(telegram_data.get('user', '{}'))
        telegram_id = str(user_info.get('id'))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user payload structure.")

    result = await db.execute(select(User).filter(User.telegram_id == telegram_id, User.role == "admin"))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    return user

@router.post("/products")
async def create_or_update_product(
    payload: ProductSchema, 
    admin_user: User = Depends(verify_admin), 
    db: AsyncSession = Depends(get_db)
):
    """
    Upserts product definition and cascades state to variants.
    """
    result = await db.execute(select(Product).filter(Product.id == payload.id))
    product = result.scalars().first()
    
    if not product:
        product = Product(id=payload.id)
        db.add(product)
        
    product.title = payload.title
    product.brand = payload.brand
    product.subtitle = payload.subtitle
    product.icon = payload.icon
    product.gradient = payload.gradient
    product.category = payload.category
    
    # Prune existing variants to maintain strict state
    await db.execute(ProductVariant.__table__.delete().where(ProductVariant.product_id == payload.id))
    
    for v in payload.variants:
        variant = ProductVariant(
            id=v.id,
            product_id=payload.id,
            duration=v.duration,
            price_label=v.priceLabel,
            raw_price=v.rawPrice
        )
        db.add(variant)

    await db.commit()
    return {"status": "success"}

@router.post("/inventory/bulk-upload")
async def bulk_upload_inventory(
    payload: ConfigUploadSchema, 
    admin_user: User = Depends(verify_admin), 
    db: AsyncSession = Depends(get_db)
):
    """
    Batch ingestion layer for inventory credentials.
    """
    items_to_insert = [
        InventoryItem(
            product_id=payload.product_id,
            variant_id=payload.variant_id,
            credentials=cred,
            status=ItemStatus.AVAILABLE
        ) for cred in payload.credentials
    ]
    
    db.add_all(items_to_insert)
    await db.commit()
    
    return {"status": "success", "inserted_count": len(items_to_insert)}