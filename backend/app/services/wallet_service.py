from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, TransactionStatus, TransactionType, Wallet


def to_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def apply_wallet_transaction(
    db: AsyncSession,
    user_id: int,
    amount,
    tx_type: TransactionType,
    ref_id: Optional[str] = None,
    description: Optional[str] = None,
    currency: str = "IRR",
    gateway: Optional[str] = None,
    auto_commit: bool = True,
) -> Wallet:
    """
    Adjust a user's wallet balance and record the transaction.

    Pass auto_commit=False when the caller manages its own transaction boundary
    (e.g., inside an atomic deposit-and-purchase flow) to avoid double-commits.
    """
    amount_decimal = to_decimal(amount)

    try:
        wallet_result = await db.execute(
            select(Wallet).where(Wallet.user_id == user_id).with_for_update()
        )
        wallet = wallet_result.scalars().first()

        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found.")

        if amount_decimal < 0 and wallet.balance < abs(amount_decimal):
            raise HTTPException(status_code=400, detail="Insufficient wallet balance.")

        wallet.balance = to_decimal(wallet.balance) + amount_decimal
        db.add(
            Transaction(
                wallet_id=wallet.id,
                amount=amount_decimal,
                currency=currency,
                gateway=gateway,
                type=tx_type,
                status=TransactionStatus.SUCCESS,
                reference_id=ref_id,
                description=description,
            )
        )

        if auto_commit:
            await db.commit()
            await db.refresh(wallet)

        return wallet
    except HTTPException:
        if auto_commit:
            await db.rollback()
        raise
    except Exception as exc:
        if auto_commit:
            await db.rollback()
        raise HTTPException(status_code=500, detail="Wallet transaction failed.") from exc
