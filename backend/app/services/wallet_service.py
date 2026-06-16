from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, TransactionType, Wallet


def to_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


async def apply_wallet_transaction(
    db: AsyncSession,
    user_id: int,
    amount,
    tx_type: TransactionType,
    ref_id: Optional[str] = None,
    description: Optional[str] = None,
) -> Wallet:
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
                type=tx_type,
                reference_id=ref_id,
                description=description,
            )
        )

        await db.commit()
        await db.refresh(wallet)
        return wallet
    except HTTPException:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Wallet transaction failed.") from exc