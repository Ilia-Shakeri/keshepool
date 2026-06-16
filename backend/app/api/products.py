from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.models import Product

router = APIRouter(prefix="/api/products", tags=["products"])

@router.get("/")
async def get_all_products(db: AsyncSession = Depends(get_db)):
    """
    Retrieves the entire product catalog including relationship variants.
    Optimized with selectinload to prevent N+1 query execution.
    """
    result = await db.execute(select(Product).options(selectinload(Product.variants)))
    products = result.scalars().all()
    
    output = []
    for p in products:
        output.append({
            "id": p.id,
            "title": p.title,
            "brand": p.brand,
            "subtitle": p.subtitle,
            "icon": p.icon,
            "gradient": p.gradient,
            "category": p.category,
            "variants": [
                {
                    "id": v.id,
                    "duration": v.duration,
                    "priceLabel": v.price_label,
                    "rawPrice": float(v.raw_price)
                } for v in p.variants
            ]
        })
    return output