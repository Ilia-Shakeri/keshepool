# ==================================================
# FILE: backend/app/api/admin.py
# ==================================================

import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from app.models import InventoryItem, ItemStatus, User
from app.core.database import get_db
from app.core.security import validate_telegram_data

router = APIRouter(prefix="/admin", tags=["admin"])

class ConfigUploadSchema(BaseModel):
    product_id: str
    plan_type: str
    credentials: List[str]

async def verify_admin(telegram_data: dict = Depends(validate_telegram_data), db: AsyncSession = Depends(get_db)):
    """
    Validates the user role from the database using securely verified Telegram data.
    Acts as an RBAC middleware dependency.
    """
    try:
        user_info = json.loads(telegram_data.get('user', '{}'))
        telegram_id = str(user_info.get('id'))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user payload structure.")

    # Check if the user exists and holds the admin role
    result = await db.execute(select(User).filter(User.telegram_id == telegram_id, User.role == "admin"))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    
    return user

@router.post("/inventory/bulk-upload")
async def bulk_upload_inventory(
    payload: ConfigUploadSchema, 
    admin_user: User = Depends(verify_admin), 
    db: AsyncSession = Depends(get_db)
):
    """
    Batch ingestion endpoint for VLESS/V2ray config URIs.
    Protected by admin RBAC middleware.
    """
    items_to_insert = [
        InventoryItem(
            product_id=payload.product_id,
            plan_type=payload.plan_type,
            credentials=cred,
            status=ItemStatus.AVAILABLE
        ) for cred in payload.credentials
    ]
    
    db.add_all(items_to_insert)
    await db.commit()
    
    return {"status": "success", "inserted_count": len(items_to_insert)}