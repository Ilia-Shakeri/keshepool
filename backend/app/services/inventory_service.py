from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import InventoryItem, ItemStatus, TransactionType
from app.services.wallet_service import process_wallet_transaction
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

def fulfill_order(db: Session, user_id: int, product_id: str, plan_type: str, price: float):
    """
    Executes order fulfillment using transaction locks.
    Deducts wallet balance and assigns inventory concurrently.
    """
    try:
        with db.begin_nested():
            # Deduct from wallet securely
            process_wallet_transaction(
                db=db, 
                user_id=user_id, 
                amount=-price, 
                tx_type=TransactionType.PURCHASE,
                ref_id=f"order_{product_id}_{plan_type}"
            )
            
            # Lock and assign an available inventory item to prevent double-selling
            item = db.query(InventoryItem).filter(
                InventoryItem.product_id == product_id,
                InventoryItem.plan_type == plan_type,
                InventoryItem.status == ItemStatus.AVAILABLE
            ).with_for_update(skip_locked=True).first()

            if not item:
                raise HTTPException(status_code=400, detail="Out of stock for this specific plan.")

            item.status = ItemStatus.ASSIGNED
            item.assigned_to_user_id = user_id
            
        db.commit()
        
        # Trigger Telegram delivery via aiogram bot instance
        # await bot.send_message(chat_id=user_id, text=f"Your config: \n{item.credentials}")
        
        return item

    except IntegrityError:
        db.rollback()
        logger.error(f"Fulfillment failed for user {user_id} and product {product_id}")
        raise HTTPException(status_code=500, detail="Order fulfillment transaction failed.")