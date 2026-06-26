from decimal import Decimal
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import redis_client
from app.models import Transaction, TransactionType, TransactionStatus, User, Wallet
from app.services.wallet_service import to_decimal

router = APIRouter(prefix="/api/pay", tags=["payments"])

class Tetra98PaymentRequest(BaseModel):
    amount: int = Field(gt=9999, le=500000000)

@router.post("/tetra98")
async def create_tetra98_payment(
    payload: Tetra98PaymentRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    # Enforce strict rate limits on payment gateway initiation
    rate_key = f"rate_limit:pay:user:{user.telegram_id}"
    
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60, nx=True)
        results = await pipe.execute()
        
    requests = results[0]
    if requests > 60:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    if not settings.TETRA98_API_URL or not settings.TETRA98_API_KEY:
        raise HTTPException(status_code=503, detail="Payment gateway is not configured.")

    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    pending_tx = Transaction(
        wallet_id=wallet.id,
        amount=to_decimal(payload.amount),
        type=TransactionType.DEPOSIT_IRR,
        status=TransactionStatus.PENDING,
        reference_id="pending",
        description="Tetra98 wallet top-up pending",
    )
    db.add(pending_tx)
    await db.commit()
    await db.refresh(pending_tx)

    gateway_payload = {
        "api_key": settings.TETRA98_API_KEY,
        "amount": payload.amount,
        "callback_url": settings.tetra98_callback_url,
        "description": f"Keshepool wallet top-up for Telegram user {user.telegram_id}",
        "order_id": str(pending_tx.id),
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(f"{settings.TETRA98_API_URL.rstrip('/')}/request", json=gateway_payload)
            response_data = response.json()
    except Exception as exc:
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = "failed_gateway_request"
        await db.commit()
        raise HTTPException(status_code=502, detail="Payment gateway request failed.") from exc

    if response.status_code != 200 or response_data.get("status") != "success":
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = "failed_gateway_response"
        await db.commit()
        raise HTTPException(status_code=400, detail="Payment gateway rejected the request.")

    authority = response_data.get("authority")
    if authority:
        pending_tx.reference_id = f"pending:{authority}"
        await db.commit()

    return {
        "status": "success",
        "paymentUrl": response_data.get("payment_url"),
        "currency": "IRR",
    }

@router.post("/tetra98/callback")
async def tetra98_payment_callback(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        data = await request.json()
    except Exception:
        form_data = await request.form()
        data = dict(form_data)

    order_id = data.get("order_id")
    transaction_id = data.get("trans_id")
    status = data.get("status")

    if status != "success" or not order_id or not transaction_id:
        return {"status": "failed", "message": "Payment was not successful."}

    try:
        order_id_int = int(order_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid order_id in callback payload.")

    tx_result = await db.execute(
        select(Transaction).where(Transaction.id == order_id_int)
    )
    pending_tx = tx_result.scalars().first()
    
    if not pending_tx or pending_tx.status != TransactionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invalid or already processed transaction.")

    verify_payload = {
        "api_key": settings.TETRA98_API_KEY,
        "trans_id": transaction_id,
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            verify_res = await client.post(f"{settings.TETRA98_API_URL.rstrip('/')}/verify", json=verify_payload)
            verify_data = verify_res.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Payment verification request failed.") from exc

    if verify_data.get("status") != "verified":
        pending_tx.status = TransactionStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    wallet_result = await db.execute(
        select(Wallet).where(Wallet.id == pending_tx.wallet_id).with_for_update()
    )
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    tx_recheck_result = await db.execute(
        select(Transaction).where(Transaction.id == int(order_id)).with_for_update()
    )
    locked_tx = tx_recheck_result.scalars().first()

    if not locked_tx or locked_tx.status != TransactionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Transaction was processed concurrently.")

    gateway_amount = Decimal(str(verify_data.get("amount", "0"))).quantize(Decimal("0.01"))
    if gateway_amount != Decimal(locked_tx.amount).quantize(Decimal("0.01")):
        locked_tx.status = TransactionStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=400, detail="Payment amount mismatch.")

    wallet.balance = to_decimal(wallet.balance) + to_decimal(locked_tx.amount)
    locked_tx.status = TransactionStatus.SUCCESS
    locked_tx.reference_id = str(transaction_id)
    locked_tx.description = "Tetra98 wallet top-up verified"

    await db.commit()
    return {"status": "ok", "message": "Payment verified and wallet charged."}