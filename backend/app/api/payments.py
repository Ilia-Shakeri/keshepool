import hashlib
import hmac
import json
import logging
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
from app.models import (
    Transaction,
    TransactionStatus,
    TransactionType,
    User,
    Wallet,
)
from app.services.inventory_service import fulfill_wallet_order
from app.services.wallet_service import to_decimal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pay", tags=["payments"])

PURCHASE_INTENT_TTL = 1800  # 30 minutes


def _purchase_intent_key(tx_id: int) -> str:
    return f"purchase_intent:tx:{tx_id}"


def _verify_hmac_signature(secret: str, body: bytes, received_sig: str) -> bool:
    """Constant-time HMAC-SHA256 comparison to prevent timing attacks."""
    if not secret or not received_sig:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig.lower())


async def _try_auto_purchase(db: AsyncSession, user: User, tx_id: int) -> None:
    """
    Execute a pending purchase intent after a confirmed deposit.
    If the purchase fails for any reason, the wallet retains the deposited funds
    and no external refund is issued.
    """
    intent_raw = await redis_client.get(_purchase_intent_key(tx_id))
    if not intent_raw:
        return

    try:
        intent = json.loads(intent_raw)
        product_id = intent.get("product_id")
        variant_id = intent.get("variant_id")
        if not product_id or not variant_id:
            return

        await fulfill_wallet_order(db=db, user=user, product_id=product_id, variant_id=variant_id)
        await redis_client.delete("cache:products:all")
        logger.info("Auto-purchase completed for user %s after deposit tx %d", user.telegram_id, tx_id)
    except HTTPException as exc:
        # Purchase failed — funds stay in wallet, no refund needed
        logger.warning(
            "Auto-purchase failed for user %s (tx %d): %s",
            user.telegram_id,
            tx_id,
            exc.detail,
        )
    except Exception:
        logger.exception("Unexpected error in auto-purchase for user %s (tx %d)", user.telegram_id, tx_id)
    finally:
        await redis_client.delete(_purchase_intent_key(tx_id))


# ── Tetra98 (IRR) ─────────────────────────────────────────────────────────────

class Tetra98PaymentRequest(BaseModel):
    amount: int = Field(gt=9999, le=500000000)
    product_id: str | None = Field(default=None, max_length=120)
    variant_id: str | None = Field(default=None, max_length=120)


@router.post("/tetra98")
async def create_tetra98_payment(
    payload: Tetra98PaymentRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rate_key = f"rate_limit:pay:user:{user.telegram_id}"
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60, nx=True)
        results = await pipe.execute()
    if results[0] > 60:
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
        currency="IRR",
        gateway="tetra98",
        type=TransactionType.DEPOSIT_IRR,
        status=TransactionStatus.PENDING,
        reference_id="pending",
        description="Tetra98 wallet top-up pending",
    )
    db.add(pending_tx)
    await db.commit()
    await db.refresh(pending_tx)

    # Persist purchase intent so the webhook can auto-execute after deposit
    if payload.product_id and payload.variant_id:
        intent = json.dumps({"product_id": payload.product_id, "variant_id": payload.variant_id})
        await redis_client.setex(_purchase_intent_key(pending_tx.id), PURCHASE_INTENT_TTL, intent)

    gateway_payload = {
        "api_key": settings.TETRA98_API_KEY,
        "amount": payload.amount,
        "callback_url": settings.tetra98_callback_url,
        "description": f"Keshepool wallet top-up for Telegram user {user.telegram_id}",
        "order_id": str(pending_tx.id),
    }

    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post(
                f"{settings.TETRA98_API_URL.rstrip('/')}/request", json=gateway_payload
            )
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
        "transactionId": pending_tx.id,
    }


@router.post("/tetra98/callback")
async def tetra98_payment_callback(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()

    # Validate HMAC signature when a webhook secret is configured
    if settings.TETRA98_WEBHOOK_SECRET:
        received_sig = request.headers.get("X-Tetra98-Signature", "")
        if not _verify_hmac_signature(settings.TETRA98_WEBHOOK_SECRET, raw_body, received_sig):
            logger.warning("Tetra98 webhook signature validation failed.")
            raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    try:
        data = json.loads(raw_body)
    except Exception:
        try:
            form_data = await request.form()
            data = dict(form_data)
        except Exception:
            raise HTTPException(status_code=400, detail="Unreadable callback payload.")

    order_id = data.get("order_id")
    transaction_id = data.get("trans_id")
    status = data.get("status")

    if status != "success" or not order_id or not transaction_id:
        return {"status": "failed", "message": "Payment was not successful."}

    try:
        order_id_int = int(order_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid order_id in callback payload.")

    tx_result = await db.execute(select(Transaction).where(Transaction.id == order_id_int))
    pending_tx = tx_result.scalars().first()

    if not pending_tx or pending_tx.status != TransactionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Invalid or already processed transaction.")

    verify_payload = {"api_key": settings.TETRA98_API_KEY, "trans_id": transaction_id}
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            verify_res = await client.post(
                f"{settings.TETRA98_API_URL.rstrip('/')}/verify", json=verify_payload
            )
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

    # Re-acquire lock on the transaction to prevent duplicate processing
    tx_locked_result = await db.execute(
        select(Transaction).where(Transaction.id == order_id_int).with_for_update()
    )
    locked_tx = tx_locked_result.scalars().first()
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

    # Retrieve the user for auto-purchase (wallet.user_id links to user)
    from app.models import User as UserModel
    user_result = await db.execute(select(UserModel).where(UserModel.id == wallet.user_id))
    user = user_result.scalars().first()
    if user:
        await _try_auto_purchase(db=db, user=user, tx_id=locked_tx.id)

    return {"status": "ok", "message": "Payment verified and wallet credited."}


# ── Crypto / USDT ─────────────────────────────────────────────────────────────

class CryptoDepositRequest(BaseModel):
    amount_usdt: Decimal = Field(gt=Decimal("0"), description="Expected USDT amount")
    product_id: str | None = Field(default=None, max_length=120)
    variant_id: str | None = Field(default=None, max_length=120)


@router.get("/crypto/deposit-address")
async def get_crypto_deposit_address(user: User = Depends(current_user)):
    """Return the platform's USDT deposit address for manual on-chain transfers."""
    if not settings.CRYPTO_DEPOSIT_ADDRESS_USDT:
        raise HTTPException(status_code=503, detail="Crypto deposits are not configured.")
    return {
        "address": settings.CRYPTO_DEPOSIT_ADDRESS_USDT,
        "network": "TRC20",
        "currency": "USDT",
    }


@router.post("/crypto/initiate")
async def initiate_crypto_deposit(
    payload: CryptoDepositRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a pending USDT deposit transaction.
    The deposit is confirmed asynchronously via the /crypto/callback webhook.
    """
    rate_key = f"rate_limit:pay:crypto:user:{user.telegram_id}"
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60, nx=True)
        results = await pipe.execute()
    if results[0] > 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    if not settings.CRYPTO_DEPOSIT_ADDRESS_USDT:
        raise HTTPException(status_code=503, detail="Crypto deposits are not configured.")

    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    pending_tx = Transaction(
        wallet_id=wallet.id,
        amount=to_decimal(payload.amount_usdt),
        currency="USDT",
        gateway="crypto_wallet",
        type=TransactionType.DEPOSIT_CRYPTO,
        status=TransactionStatus.PENDING,
        reference_id="awaiting_confirmation",
        description=f"USDT deposit initiated — awaiting on-chain confirmation",
    )
    db.add(pending_tx)
    await db.commit()
    await db.refresh(pending_tx)

    if payload.product_id and payload.variant_id:
        intent = json.dumps({"product_id": payload.product_id, "variant_id": payload.variant_id})
        await redis_client.setex(_purchase_intent_key(pending_tx.id), PURCHASE_INTENT_TTL, intent)

    return {
        "status": "pending",
        "transactionId": pending_tx.id,
        "depositAddress": settings.CRYPTO_DEPOSIT_ADDRESS_USDT,
        "network": "TRC20",
        "expectedAmount": str(payload.amount_usdt),
        "currency": "USDT",
        "message": "Send the exact amount to the deposit address. Your balance will be credited after confirmation.",
    }


class CryptoWebhookPayload(BaseModel):
    transaction_id: int
    tx_hash: str
    amount_usdt: str
    status: str


@router.post("/crypto/callback")
async def crypto_payment_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint called by the on-chain monitoring service upon USDT payment confirmation.
    Protected by HMAC-SHA256 signature on the raw request body.
    """
    raw_body = await request.body()

    if settings.CRYPTO_WEBHOOK_SECRET:
        received_sig = request.headers.get("X-Crypto-Signature", "")
        if not _verify_hmac_signature(settings.CRYPTO_WEBHOOK_SECRET, raw_body, received_sig):
            logger.warning("Crypto webhook signature validation failed.")
            raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    try:
        data = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    tx_id = data.get("transaction_id")
    tx_hash = data.get("tx_hash", "")
    amount_usdt = data.get("amount_usdt", "0")
    webhook_status = data.get("status", "")

    if webhook_status != "confirmed" or not tx_id or not tx_hash:
        return {"status": "ignored", "message": "Non-confirmed event skipped."}

    # Idempotency guard — reject duplicate webhook deliveries
    idempotency_key = f"crypto_webhook_processed:{tx_hash}"
    was_set = await redis_client.set(idempotency_key, "1", nx=True, ex=86400)
    if not was_set:
        return {"status": "ok", "message": "Already processed."}

    tx_result = await db.execute(select(Transaction).where(Transaction.id == int(tx_id)).with_for_update())
    pending_tx = tx_result.scalars().first()
    if not pending_tx or pending_tx.status != TransactionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Transaction not found or already processed.")

    confirmed_amount = Decimal(str(amount_usdt)).quantize(Decimal("0.01"))
    expected_amount = Decimal(pending_tx.amount).quantize(Decimal("0.01"))
    if confirmed_amount < expected_amount:
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.description = f"Underpayment: received {confirmed_amount} USDT, expected {expected_amount} USDT"
        await db.commit()
        raise HTTPException(status_code=400, detail="Confirmed amount is less than expected.")

    wallet_result = await db.execute(
        select(Wallet).where(Wallet.id == pending_tx.wallet_id).with_for_update()
    )
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    wallet.balance = to_decimal(wallet.balance) + to_decimal(pending_tx.amount)
    pending_tx.status = TransactionStatus.SUCCESS
    pending_tx.reference_id = tx_hash
    pending_tx.description = f"USDT deposit confirmed — tx hash: {tx_hash[:16]}..."
    await db.commit()

    from app.models import User as UserModel
    user_result = await db.execute(select(UserModel).where(UserModel.id == wallet.user_id))
    user = user_result.scalars().first()
    if user:
        await _try_auto_purchase(db=db, user=user, tx_id=pending_tx.id)

    return {"status": "ok", "message": "Crypto deposit confirmed and wallet credited."}
