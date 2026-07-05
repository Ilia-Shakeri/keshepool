import hashlib
import hmac
import json
import logging
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.users import current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import redis_client
from app.services.rate_service import get_usdt_rate
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

# Tetra98 always lives at this base URL.
TETRA98_BASE = "https://tetra98.com"
DEFAULT_USDT_TRC20_DEPOSIT_ADDRESS = "TP1Yadt466uCb5pBQTbMZ8jqRk7TpZowXH"


def _purchase_intent_key(tx_id: int) -> str:
    return f"purchase_intent:tx:{tx_id}"


def _verify_hmac_signature(secret: str, body: bytes, received_sig: str) -> bool:
    """Constant-time HMAC-SHA256 comparison to prevent timing attacks."""
    if not secret or not received_sig:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig.lower())


def _usdt_trc20_deposit_address() -> str:
    """Return the configured USDT TRC20 deposit address with a production fallback."""
    return settings.CRYPTO_DEPOSIT_ADDRESS_USDT or DEFAULT_USDT_TRC20_DEPOSIT_ADDRESS


async def _try_auto_purchase(db: AsyncSession, user: User, tx_id: int) -> None:
    """
    Execute a pending purchase intent after a confirmed deposit.
    If the purchase fails, the wallet retains the deposited funds —
    no external refund is needed.
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
        logger.info("Auto-purchase done for user %s after deposit tx %d", user.telegram_id, tx_id)
    except HTTPException as exc:
        logger.warning("Auto-purchase failed for user %s (tx %d): %s", user.telegram_id, tx_id, exc.detail)
    except Exception:
        logger.exception("Unexpected error in auto-purchase for user %s (tx %d)", user.telegram_id, tx_id)
    finally:
        await redis_client.delete(_purchase_intent_key(tx_id))


# ── Tetra98 (IRR) ─────────────────────────────────────────────────────────────
#
# API reference (from vendor dashboard):
#   Create : POST https://tetra98.com/api/create_order
#            body: { ApiKey, Hash_id, Amount, Description, Email, Mobile, CallbackURL }
#            200 success: { status:"100", Authority, payment_url_web, payment_url_bot, tracking_id }
#
#   Callback (Tetra98 → us):
#            POST <CallbackURL>
#            body: { authority, hash_id, status:100 }
#
#   Verify  : POST https://tetra98.com/api/verify
#             body: { ApiKey, authority }
#             200 success: { status:"100" }

class Tetra98PaymentRequest(BaseModel):
    amount: int = Field(gt=9999, le=50000000, description="Amount in Toman (minimum 10,000)")
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
    if results[0] > 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    if not settings.TETRA98_API_KEY:
        raise HTTPException(status_code=503, detail="Payment gateway is not configured.")

    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    # Create a pending transaction first so we have a DB-backed ID to use as Hash_id.
    # amount is stored in Toman to match the wallet balance unit.
    pending_tx = Transaction(
        wallet_id=wallet.id,
        amount=to_decimal(payload.amount),
        currency="IRR",
        gateway="tetra98",
        type=TransactionType.DEPOSIT_IRR,
        status=TransactionStatus.PENDING,
        reference_id="pending",
        description="Tetra98 IRR deposit — awaiting payment",
    )
    db.add(pending_tx)
    await db.commit()
    await db.refresh(pending_tx)

    # Store optional purchase intent so the callback can auto-execute it
    if payload.product_id and payload.variant_id:
        intent = json.dumps({"product_id": payload.product_id, "variant_id": payload.variant_id})
        await redis_client.setex(_purchase_intent_key(pending_tx.id), PURCHASE_INTENT_TTL, intent)

    # Tetra98 expects Amount in Rials; payload.amount is in Toman → multiply by 10.
    gateway_payload = {
        "ApiKey": settings.TETRA98_API_KEY,
        "Hash_id": str(pending_tx.id),      # our transaction ID; returned as hash_id in callback
        "Amount": payload.amount * 10,
        "Description": f"Keshepool deposit — user {user.telegram_id}",
        "Email": "",
        "Mobile": "",
        "CallbackURL": settings.tetra98_callback_url,
    }

    logger.info("Tetra98 create_order for tx %d, amount %d Toman (%d IRR)", pending_tx.id, payload.amount, payload.amount * 10)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{TETRA98_BASE}/api/create_order",
                json=gateway_payload,
            )
            response_data = response.json()
    except Exception as exc:
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = "gateway_request_failed"
        await db.commit()
        logger.error("Tetra98 create_order HTTP error for tx %d: %s", pending_tx.id, exc)
        raise HTTPException(status_code=502, detail="Payment gateway request failed.") from exc

    logger.info("Tetra98 create_order response for tx %d: %s", pending_tx.id, response_data)

    # Tetra98 returns status "100" (string) for success
    if response.status_code != 200 or str(response_data.get("status", "")) != "100":
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = f"gateway_error:{response_data.get('status', 'unknown')}"
        await db.commit()
        error_msg = response_data.get("message") or response_data.get("error") or "Gateway rejected the request."
        raise HTTPException(status_code=400, detail=str(error_msg))

    authority = response_data.get("Authority") or response_data.get("authority", "")
    pending_tx.reference_id = f"authority:{authority}"
    await db.commit()

    return {
        "status": "success",
        "transactionId": pending_tx.id,
        "authority": authority,
        "paymentUrlWeb": response_data.get("payment_url_web", ""),
        "paymentUrlBot": response_data.get("payment_url_bot", ""),
        "trackingId": response_data.get("tracking_id", ""),
        "currency": "IRR",
    }


@router.post("/tetra98/callback")
async def tetra98_payment_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Tetra98 POSTs to this URL after a payment attempt.
    Payload: { authority, hash_id, status }
    status == 100 means the user completed the payment flow; we then call /verify to confirm.
    """
    raw_body = await request.body()

    if settings.TETRA98_WEBHOOK_SECRET:
        received_sig = request.headers.get(settings.TETRA98_SIG_HEADER, "")
        if not _verify_hmac_signature(settings.TETRA98_WEBHOOK_SECRET, raw_body, received_sig):
            logger.warning("Tetra98 callback signature validation failed.")
            raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    # Parse JSON body; Tetra98 sends application/json
    try:
        data = json.loads(raw_body)
    except Exception:
        # Fallback: some gateways send form-encoded data
        try:
            form_data = await request.form()
            data = dict(form_data)
        except Exception:
            logger.warning("Tetra98 callback: unreadable body")
            raise HTTPException(status_code=400, detail="Unreadable callback payload.")

    authority = data.get("authority") or data.get("Authority", "")
    hash_id = str(data.get("hash_id") or data.get("Hash_id") or "")
    callback_status = data.get("status")

    logger.info("Tetra98 callback received: authority=%s hash_id=%s status=%s", authority, hash_id, callback_status)

    # status 100 (int or string) = user completed payment; anything else = cancelled/failed
    if str(callback_status) != "100" or not authority or not hash_id:
        logger.info("Tetra98 callback: non-success status=%s, skipping.", callback_status)
        return {"status": "failed", "message": "Payment was not completed."}

    # Resolve our transaction via the hash_id we originally sent as Hash_id
    try:
        tx_id = int(hash_id)
    except ValueError:
        logger.warning("Tetra98 callback: invalid hash_id=%s", hash_id)
        raise HTTPException(status_code=400, detail="Invalid hash_id in callback.")

    tx_result = await db.execute(select(Transaction).where(Transaction.id == tx_id))
    pending_tx = tx_result.scalars().first()

    if not pending_tx:
        logger.warning("Tetra98 callback: transaction %d not found", tx_id)
        raise HTTPException(status_code=400, detail="Transaction not found.")

    if pending_tx.status != TransactionStatus.PENDING:
        # Already processed (idempotent response — Tetra98 may retry callbacks)
        logger.info("Tetra98 callback: tx %d already in status %s", tx_id, pending_tx.status)
        return {"status": "ok", "message": "Already processed."}

    # Verify the payment with Tetra98 before crediting the wallet
    verify_payload = {
        "ApiKey": settings.TETRA98_API_KEY,
        "authority": authority,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            verify_res = await client.post(
                f"{TETRA98_BASE}/api/verify",
                json=verify_payload,
            )
            verify_data = verify_res.json()
    except Exception as exc:
        logger.error("Tetra98 verify HTTP error for tx %d: %s", tx_id, exc)
        raise HTTPException(status_code=502, detail="Payment verification request failed.") from exc

    logger.info("Tetra98 verify response for tx %d: %s", tx_id, verify_data)

    # Verify also returns "100" for success
    if str(verify_data.get("status", "")) != "100":
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = f"verify_failed:{authority}"
        await db.commit()
        logger.warning("Tetra98 verify failed for tx %d: %s", tx_id, verify_data)
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    # Acquire row-level locks in deterministic order to prevent deadlocks
    wallet_result = await db.execute(
        select(Wallet).where(Wallet.id == pending_tx.wallet_id).with_for_update()
    )
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    locked_tx_result = await db.execute(
        select(Transaction).where(Transaction.id == tx_id).with_for_update()
    )
    locked_tx = locked_tx_result.scalars().first()
    if not locked_tx or locked_tx.status != TransactionStatus.PENDING:
        # Concurrent request already processed this
        return {"status": "ok", "message": "Processed concurrently."}

    wallet.balance = to_decimal(wallet.balance) + to_decimal(locked_tx.amount)
    locked_tx.status = TransactionStatus.SUCCESS
    locked_tx.reference_id = authority
    locked_tx.description = f"Tetra98 deposit verified — {locked_tx.amount} Toman (authority: {authority[:12]}...)"
    await db.commit()

    logger.info("Tetra98: tx %d credited %.2f Toman to wallet %d", tx_id, locked_tx.amount, wallet.id)

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


@router.get("/crypto/rate")
async def get_crypto_rate(user: User = Depends(current_user)):
    """Live USDT→Toman rate for the deposit UI to display the equivalent value."""
    rate = await get_usdt_rate()
    return {"tomanPerUsdt": int(rate), "base": "USDT", "quote": "TOMAN"}


@router.get("/crypto/deposit-address")
async def get_crypto_deposit_address(user: User = Depends(current_user)):
    return {
        "address": _usdt_trc20_deposit_address(),
        "network": "TRC20",
        "currency": "USDT",
    }


@router.post("/crypto/initiate")
async def initiate_crypto_deposit(
    payload: CryptoDepositRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rate_key = f"rate_limit:pay:crypto:user:{user.telegram_id}"
    async with redis_client.pipeline(transaction=True) as pipe:
        pipe.incr(rate_key)
        pipe.expire(rate_key, 60, nx=True)
        results = await pipe.execute()
    if results[0] > 10:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

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
        description="USDT deposit — awaiting on-chain confirmation",
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
        "depositAddress": _usdt_trc20_deposit_address(),
        "network": "TRC20",
        "expectedAmount": str(payload.amount_usdt),
        "currency": "USDT",
        "message": "Send the exact amount to the deposit address. Balance is credited after network confirmation.",
    }


@router.post("/crypto/callback")
async def crypto_payment_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook called by the on-chain monitoring service upon USDT payment confirmation.
    Protected by HMAC-SHA256 on the raw request body.
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

    # Validate identifiers before touching Redis/DB so malformed payloads fail cleanly
    try:
        tx_id_int = int(tx_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid transaction_id in payload.")

    try:
        confirmed_amount = Decimal(str(amount_usdt)).quantize(Decimal("0.000001"))
    except (InvalidOperation, TypeError):
        raise HTTPException(status_code=400, detail="Invalid amount_usdt in payload.")

    # Idempotency guard — safe against duplicate webhook deliveries
    idempotency_key = f"crypto_webhook_processed:{tx_hash}"
    was_set = await redis_client.set(idempotency_key, "1", nx=True, ex=86400)
    if not was_set:
        return {"status": "ok", "message": "Already processed."}

    tx_result = await db.execute(
        select(Transaction).where(Transaction.id == tx_id_int).with_for_update()
    )
    pending_tx = tx_result.scalars().first()
    if not pending_tx or pending_tx.status != TransactionStatus.PENDING:
        raise HTTPException(status_code=400, detail="Transaction not found or already processed.")

    expected_amount = Decimal(pending_tx.amount).quantize(Decimal("0.000001"))
    if confirmed_amount < expected_amount:
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.description = f"Underpayment: received {confirmed_amount} USDT, expected {expected_amount}"
        await db.commit()
        raise HTTPException(status_code=400, detail="Confirmed amount is less than expected.")

    wallet_result = await db.execute(
        select(Wallet).where(Wallet.id == pending_tx.wallet_id).with_for_update()
    )
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    # Convert USDT to Toman using the live exchange rate before crediting the wallet.
    # Transaction.amount is stored in USDT; wallet.balance is always in Toman.
    rate = await get_usdt_rate()
    toman_credit = to_decimal(pending_tx.amount) * rate
    wallet.balance = to_decimal(wallet.balance) + toman_credit
    pending_tx.status = TransactionStatus.SUCCESS
    pending_tx.reference_id = tx_hash
    pending_tx.description = f"USDT deposit confirmed — {confirmed_amount} USDT @ {int(rate):,} T/USDT — {tx_hash[:16]}..."
    await db.commit()

    from app.models import User as UserModel
    user_result = await db.execute(select(UserModel).where(UserModel.id == wallet.user_id))
    user = user_result.scalars().first()
    if user:
        await _try_auto_purchase(db=db, user=user, tx_id=pending_tx.id)

    return {"status": "ok", "message": "Crypto deposit confirmed and wallet credited."}
