from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Wallet, Transaction, TransactionType
from fastapi import HTTPException

def process_wallet_transaction(db: Session, user_id: int, amount: float, tx_type: TransactionType, ref_id: str = None):
    """
    Executes a wallet transaction with strict ACID compliance.
    Locks the wallet row to prevent race conditions during concurrent requests.
    """
    try:
        # Start transaction block
        with db.begin_nested():
            # Lock the specific wallet row for update
            wallet = db.query(Wallet).filter(Wallet.user_id == user_id).with_for_update().first()
            
            if not wallet:
                raise HTTPException(status_code=404, detail="Wallet not found.")
                
            # Validate sufficient funds for deductions
            if amount < 0 and wallet.balance < abs(amount):
                raise HTTPException(status_code=400, detail="Insufficient funds.")
                
            # Apply balance change
            wallet.balance += amount
            
            # Record the audit trail
            transaction = Transaction(
                wallet_id=wallet.id,
                amount=amount,
                type=tx_type,
                reference_id=ref_id
            )
            db.add(transaction)
            
        db.commit()
        return wallet
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database transaction failed.")