import hashlib
import hmac
import json
import logging
import re
import secrets
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
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
from app.services.cache_service import check_rate_limit, invalidate_catalog_cache, namespaced_key
from app.services.wallet_service import to_decimal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pay", tags=["payments"])

PURCHASE_INTENT_TTL = 1800  # 30 minutes
CRYPTO_WEBHOOK_LOCK_TTL = 120
CRYPTO_WEBHOOK_PROCESSED_TTL = 7 * 24 * 60 * 60
USDT_QUANTUM = Decimal("0.000001")


def _purchase_intent_key(tx_id: int) -> str:
    return namespaced_key(f"purchase-intent:tx:{tx_id}")


def _tetra98_url(path: str) -> str:
    base_url = settings.TETRA98_API_URL.strip().rstrip("/")
    if not base_url:
        raise HTTPException(status_code=503, detail="Payment gateway URL is not configured.")
    return f"{base_url}/{path.lstrip('/')}"


def _validated_tetra98_authority(value: object) -> str:
    authority = str(value or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,200}", authority):
        return ""
    return authority


def _validated_tetra98_redirect_url(
    value: object,
    *,
    kind: str,
    authority: str,
) -> str:
    raw_url = str(value or "").strip()
    if not raw_url or any(ord(char) < 32 for char in raw_url):
        return ""
    try:
        parsed = urlparse(raw_url)
        configured = urlparse(settings.TETRA98_API_URL.strip())
        parsed_port = parsed.port or 443
        configured_port = configured.port or 443
    except ValueError:
        return ""
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        return ""

    if kind == "web":
        if (
            not configured.hostname
            or parsed.hostname.lower() != configured.hostname.lower()
            or parsed_port != configured_port
            or parsed.path.rstrip("/") != f"/payment/{authority}"
            or parsed.query
        ):
            return ""
        return raw_url

    if kind == "bot":
        try:
            start_values = parse_qs(parsed.query, strict_parsing=True).get("start", [])
        except ValueError:
            return ""
        if (
            parsed.hostname.lower() not in {"t.me", "telegram.me", "www.telegram.me"}
            or parsed.path.rstrip("/").casefold() != "/tetra98_bot".casefold()
            or start_values != [f"pay_{authority}"]
        ):
            return ""
        return raw_url

    return ""


def _verify_hmac_signature(secret: str, body: bytes, received_sig: str) -> bool:
    """Constant-time HMAC-SHA256 comparison to prevent timing attacks."""
    if not secret or not received_sig:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received_sig.lower())


def _usdt_trc20_deposit_address() -> str:
    """Return only an explicitly configured USDT TRC20 deposit address."""
    address = settings.CRYPTO_DEPOSIT_ADDRESS_USDT.strip()
    if not address:
        raise HTTPException(status_code=503, detail="Crypto deposits are not configured.")
    return address


def _require_production_webhook_secret(secret: str, gateway: str) -> None:
    if settings.ENVIRONMENT.lower() == "production" and not secret:
        raise HTTPException(
            status_code=503,
            detail=f"{gateway} webhook verification is not configured.",
        )


def _usdt_amount(value: object) -> Decimal:
    try:
        return Decimal(str(value)).quantize(USDT_QUANTUM)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid USDT amount.") from exc


async def _store_purchase_intent(tx_id: int, product_id: str | None, variant_id: str | None) -> None:
    if not product_id or not variant_id:
        return
    intent = json.dumps({"product_id": product_id, "variant_id": variant_id})
    try:
        await redis_client.setex(_purchase_intent_key(tx_id), PURCHASE_INTENT_TTL, intent)
    except RedisError:
        logger.exception("Purchase intent cache write failed for transaction %d", tx_id)


def _webhook_cache_key(provider: str, state: str, reference: str) -> str:
    reference_key = hashlib.sha256(reference.encode()).hexdigest()
    return namespaced_key(f"webhook:{provider}:{state}:{reference_key}")


async def _reserve_webhook(provider: str, reference: str) -> tuple[str, bool]:
    processed_key = _webhook_cache_key(provider, "processed", reference)
    lock_key = _webhook_cache_key(provider, "processing", reference)
    token = secrets.token_urlsafe(24)
    try:
        if await redis_client.exists(processed_key):
            return token, True
        acquired = await redis_client.set(lock_key, token, nx=True, ex=CRYPTO_WEBHOOK_LOCK_TTL)
    except RedisError as exc:
        raise HTTPException(
            status_code=503,
            detail="Webhook idempotency service is unavailable; retry later.",
        ) from exc
    if not acquired:
        raise HTTPException(status_code=409, detail="Webhook is already being processed.")
    return token, False


async def _release_webhook(provider: str, reference: str, token: str) -> None:
    lock_key = _webhook_cache_key(provider, "processing", reference)
    try:
        await redis_client.eval(
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end",
            1,
            lock_key,
            token,
        )
    except RedisError:
        logger.exception("%s webhook lock release failed", provider)


async def _mark_webhook_processed(provider: str, reference: str) -> None:
    try:
        await redis_client.setex(
            _webhook_cache_key(provider, "processed", reference),
            CRYPTO_WEBHOOK_PROCESSED_TTL,
            "1",
        )
    except RedisError:
        # The database transaction state remains the source of truth.
        logger.exception("%s webhook completion cache write failed", provider)


async def _reserve_crypto_webhook(tx_hash: str) -> tuple[str, bool]:
    return await _reserve_webhook("crypto", tx_hash)


async def _release_crypto_webhook(tx_hash: str, token: str) -> None:
    await _release_webhook("crypto", tx_hash, token)


async def _mark_crypto_webhook_processed(tx_hash: str) -> None:
    await _mark_webhook_processed("crypto", tx_hash)


async def _try_auto_purchase(db: AsyncSession, user: User, tx_id: int) -> None:
    """
    Execute a pending purchase intent after a confirmed deposit.
    If the purchase fails, the wallet retains the deposited funds —
    no external refund is needed.
    """
    try:
        intent_raw = await redis_client.get(_purchase_intent_key(tx_id))
    except RedisError:
        logger.exception("Purchase intent cache read failed for transaction %d", tx_id)
        return
    if not intent_raw:
        return
    try:
        intent = json.loads(intent_raw)
        product_id = intent.get("product_id")
        variant_id = intent.get("variant_id")
        if not product_id or not variant_id:
            return
        await fulfill_wallet_order(db=db, user=user, product_id=product_id, variant_id=variant_id)
        try:
            await invalidate_catalog_cache()
        except RedisError:
            logger.exception("Catalog cache clear failed after auto-purchase")
        logger.info("Auto-purchase done for user %s after deposit tx %d", user.telegram_id, tx_id)
    except HTTPException as exc:
        logger.warning("Auto-purchase failed for user %s (tx %d): %s", user.telegram_id, tx_id, exc.detail)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.exception("Unexpected error in auto-purchase for user %s (tx %d)", user.telegram_id, tx_id)
    finally:
        try:
            await redis_client.delete(_purchase_intent_key(tx_id))
        except RedisError:
            logger.exception("Purchase intent cache clear failed for transaction %d", tx_id)


# ── Tetra98 (IRR) ─────────────────────────────────────────────────────────────
#
# API reference (from vendor dashboard, relative to configured TETRA98_API_URL):
#   Create : POST /api/create_order
#            body: { ApiKey, Hash_id, Amount, Description, Email, Mobile, CallbackURL }
#            200 success: { status:"100", Authority, payment_url_web, payment_url_bot, tracking_id }
#
#   Callback (gateway → us):
#            POST <CallbackURL>
#            body: { authority, hashid, status:100 }
#
#   Verify  : POST /api/verify
#             body: { ApiKey, authority }
#             200 success: { status:"100", hash_id, authority }

class Tetra98PaymentRequest(BaseModel):
    amount: int = Field(gt=9999, le=50000000, description="Amount in تومان (minimum 10,000)")
    product_id: str | None = Field(default=None, max_length=120)
    variant_id: str | None = Field(default=None, max_length=120)


@router.post("/tetra98")
async def create_tetra98_payment(
    payload: Tetra98PaymentRequest,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    rate_limit = await check_rate_limit(
        "payment-tetra98",
        user.telegram_id,
        limit=10,
        window_seconds=60,
    )
    if not rate_limit.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    if not settings.TETRA98_API_KEY:
        raise HTTPException(status_code=503, detail="Payment gateway is not configured.")

    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    # Create a pending transaction first so we have a DB-backed ID to use as Hash_id.
    # Amount is stored in the wallet balance unit.
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

    await _store_purchase_intent(
        pending_tx.id,
        payload.product_id,
        payload.variant_id,
    )

    # Tetra98 expects Amount in Rials; multiply the wallet unit by 10.
    gateway_payload = {
        "ApiKey": settings.TETRA98_API_KEY,
        "Hash_id": str(pending_tx.id),      # our transaction ID; returned as hash_id in callback
        "Amount": payload.amount * 10,
        "Description": f"Keshepool deposit — user {user.telegram_id}",
        "Email": "",
        "Mobile": "",
        "CallbackURL": settings.tetra98_callback_url,
    }

    logger.info("Tetra98 create_order for tx %d, amount %d تومان (%d IRR)", pending_tx.id, payload.amount, payload.amount * 10)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                _tetra98_url("api/create_order"),
                json=gateway_payload,
            )
            response_data = response.json()
    except Exception as exc:
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = "gateway_request_failed"
        await db.commit()
        logger.error("Tetra98 create_order HTTP error for tx %d: %s", pending_tx.id, exc)
        raise HTTPException(status_code=502, detail="Payment gateway request failed.") from exc

    logger.info(
        "Tetra98 create_order response for tx %d: HTTP %d, status=%s",
        pending_tx.id,
        response.status_code,
        response_data.get("status"),
    )

    # Tetra98 returns status "100" (string) for success
    if response.status_code != 200 or str(response_data.get("status", "")) != "100":
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = f"gateway_error:{response_data.get('status', 'unknown')}"
        await db.commit()
        error_msg = response_data.get("message") or response_data.get("error") or "Gateway rejected the request."
        raise HTTPException(status_code=400, detail=str(error_msg))

    authority = _validated_tetra98_authority(
        response_data.get("Authority") or response_data.get("authority")
    )
    if not authority:
        pending_tx.status = TransactionStatus.FAILED
        pending_tx.reference_id = "gateway_error:missing_authority"
        await db.commit()
        raise HTTPException(status_code=502, detail="Payment gateway returned no authority.")
    pending_tx.reference_id = f"authority:{authority}"
    await db.commit()

    payment_url_web = _validated_tetra98_redirect_url(
        response_data.get("payment_url_web"),
        kind="web",
        authority=authority,
    )
    payment_url_bot = _validated_tetra98_redirect_url(
        response_data.get("payment_url_bot"),
        kind="bot",
        authority=authority,
    )
    if not payment_url_web and not payment_url_bot:
        logger.error("Tetra98 returned no trusted payment redirect for tx %d", pending_tx.id)
        raise HTTPException(status_code=502, detail="Payment gateway returned no trusted payment URL.")

    return {
        "status": "success",
        "transactionId": pending_tx.id,
        "authority": authority,
        "paymentUrlWeb": payment_url_web,
        "paymentUrlBot": payment_url_bot,
        "trackingId": response_data.get("tracking_id", ""),
        "currency": "IRR",
    }


async def _credit_tetra98_transaction(
    db: AsyncSession,
    tx_id: int,
    wallet_id: int,
    authority: str,
) -> dict[str, str]:
    token, already_processed = await _reserve_webhook("tetra98", authority)
    if already_processed:
        return {"status": "ok", "message": "Already processed."}

    committed = False
    wallet_user_id: int | None = None
    try:
        # All vendor calls finish before this deterministic lock order begins.
        wallet_result = await db.execute(
            select(Wallet).where(Wallet.id == wallet_id).with_for_update()
        )
        wallet = wallet_result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found.")

        locked_tx_result = await db.execute(
            select(Transaction).where(Transaction.id == tx_id).with_for_update()
        )
        locked_tx = locked_tx_result.scalars().first()
        if not locked_tx:
            raise HTTPException(status_code=400, detail="Transaction not found.")
        if locked_tx.status != TransactionStatus.PENDING:
            if locked_tx.status == TransactionStatus.SUCCESS and locked_tx.reference_id == authority:
                await db.rollback()
                return {"status": "ok", "message": "Already processed."}
            raise HTTPException(status_code=409, detail="Transaction is not pending.")
        if (
            locked_tx.wallet_id != wallet.id
            or locked_tx.type != TransactionType.DEPOSIT_IRR
            or locked_tx.gateway != "tetra98"
            or locked_tx.currency.upper() != "IRR"
            or locked_tx.reference_id != f"authority:{authority}"
        ):
            raise HTTPException(status_code=400, detail="Callback does not match the transaction.")

        duplicate_result = await db.execute(
            select(Transaction.id).where(
                Transaction.id != locked_tx.id,
                Transaction.gateway == "tetra98",
                Transaction.reference_id == authority,
                Transaction.status == TransactionStatus.SUCCESS,
            )
        )
        if duplicate_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Gateway authority was already used.")

        wallet.balance = to_decimal(wallet.balance) + to_decimal(locked_tx.amount)
        locked_tx.status = TransactionStatus.SUCCESS
        locked_tx.reference_id = authority
        locked_tx.description = f"Tetra98 deposit verified: transaction {tx_id}"
        wallet_user_id = wallet.user_id
        await db.commit()
        committed = True
        await _mark_webhook_processed("tetra98", authority)
    except HTTPException:
        if not committed:
            await db.rollback()
        raise
    except Exception as exc:
        if not committed:
            await db.rollback()
        logger.exception("Tetra98 credit failed for transaction %d", tx_id)
        raise HTTPException(status_code=500, detail="Payment credit failed.") from exc
    finally:
        await _release_webhook("tetra98", authority, token)

    logger.info("Tetra98 transaction %d credited to wallet %d", tx_id, wallet_id)
    if wallet_user_id is not None:
        try:
            user_result = await db.execute(select(User).where(User.id == wallet_user_id))
            user = user_result.scalars().first()
            if user:
                await _try_auto_purchase(db=db, user=user, tx_id=tx_id)
        except Exception:
            logger.exception("Post-deposit purchase check failed for transaction %d", tx_id)

    return {"status": "ok", "message": "Payment verified and wallet credited."}


@router.post("/tetra98/callback")
async def tetra98_payment_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Tetra98 POSTs to this URL after a payment attempt.
    Payload: { authority, hashid, status }
    status == 100 means the user completed the payment flow; we then call /verify to confirm.
    """
    raw_body = await request.body()

    # The vendor does not send a signature header. When an operator-configured
    # signature is present we enforce it, while server-to-server /verify remains
    # the required authentication step for the documented callback flow.
    if settings.TETRA98_WEBHOOK_SECRET:
        received_sig = request.headers.get(settings.TETRA98_SIG_HEADER, "")
        if not _verify_hmac_signature(settings.TETRA98_WEBHOOK_SECRET, raw_body, received_sig):
            logger.warning("Tetra98 callback signature validation failed.")
            raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    if not settings.TETRA98_API_KEY:
        raise HTTPException(status_code=503, detail="Payment gateway is not configured.")

    # Parse JSON body; Tetra98 sends application/json
    try:
        data = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Fallback: some gateways send form-encoded data
        try:
            form_data = await request.form()
            data = dict(form_data)
        except Exception as exc:
            logger.warning("Tetra98 callback: unreadable body")
            raise HTTPException(status_code=400, detail="Unreadable callback payload.") from exc

    authority = _validated_tetra98_authority(
        data.get("authority") or data.get("Authority")
    )
    hash_id = str(
        data.get("hashid")
        or data.get("hash_id")
        or data.get("Hash_id")
        or ""
    ).strip()
    callback_status = data.get("status")

    logger.info("Tetra98 callback received for hash_id=%s status=%s", hash_id, callback_status)

    # status 100 (int or string) = user completed payment; anything else = cancelled/failed
    if str(callback_status) != "100":
        logger.info("Tetra98 callback: non-success status=%s, skipping.", callback_status)
        return {"status": "failed", "message": "Payment was not completed."}

    if not authority:
        raise HTTPException(status_code=400, detail="Invalid authority in callback.")
    if not hash_id:
        raise HTTPException(status_code=400, detail="Missing hash_id in callback.")

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
        if pending_tx.status == TransactionStatus.SUCCESS and pending_tx.reference_id == authority:
            return {"status": "ok", "message": "Already processed."}
        raise HTTPException(status_code=409, detail="Transaction is not pending.")

    if (
        pending_tx.type != TransactionType.DEPOSIT_IRR
        or pending_tx.gateway != "tetra98"
        or pending_tx.currency.upper() != "IRR"
        or pending_tx.reference_id != f"authority:{authority}"
    ):
        raise HTTPException(status_code=400, detail="Callback does not match the transaction.")

    # Verify the payment with Tetra98 before crediting the wallet
    verify_payload = {
        "ApiKey": settings.TETRA98_API_KEY,
        "authority": authority,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            verify_res = await client.post(
                _tetra98_url("api/verify"),
                json=verify_payload,
            )
            verify_data = verify_res.json()
    except Exception as exc:
        logger.error("Tetra98 verify HTTP error for tx %d: %s", tx_id, exc)
        raise HTTPException(status_code=502, detail="Payment verification request failed.") from exc

    logger.info(
        "Tetra98 verify response for tx %d: HTTP %d, status=%s",
        tx_id,
        verify_res.status_code,
        verify_data.get("status"),
    )

    # Verify also returns "100" for success
    if verify_res.status_code != 200 or str(verify_data.get("status", "")) != "100":
        await db.rollback()
        logger.warning("Tetra98 verify rejected transaction %d", tx_id)
        raise HTTPException(status_code=400, detail="Payment verification failed.")

    verified_hash_id = str(
        verify_data.get("hash_id")
        or verify_data.get("hashid")
        or verify_data.get("Hash_id")
        or ""
    ).strip()
    verified_authority = str(
        verify_data.get("authority") or verify_data.get("Authority") or ""
    ).strip()
    if verified_hash_id != str(tx_id) or verified_authority != authority:
        raise HTTPException(
            status_code=400,
            detail="Verified payment identity does not match the transaction.",
        )

    verified_amount = verify_data.get("Amount", verify_data.get("amount"))
    if verified_amount is not None:
        try:
            expected_rials = Decimal(pending_tx.amount) * Decimal("10")
            if Decimal(str(verified_amount)) != expected_rials:
                raise HTTPException(
                    status_code=400,
                    detail="Verified amount does not match the transaction.",
                )
        except InvalidOperation as exc:
            raise HTTPException(status_code=400, detail="Invalid verified amount.") from exc

    return await _credit_tetra98_transaction(
        db,
        tx_id=tx_id,
        wallet_id=pending_tx.wallet_id,
        authority=authority,
    )

# ── Crypto / USDT ─────────────────────────────────────────────────────────────

def _validate_pending_crypto_transaction(
    transaction: Transaction,
    confirmed_amount: Decimal,
) -> None:
    if (
        transaction.type != TransactionType.DEPOSIT_CRYPTO
        or transaction.gateway != "crypto_wallet"
        or transaction.currency.upper() != "USDT"
        or transaction.reference_id != "awaiting_confirmation"
    ):
        raise HTTPException(status_code=400, detail="Webhook does not match the transaction.")

    if _usdt_amount(transaction.amount) != confirmed_amount:
        raise HTTPException(status_code=400, detail="Confirmed amount does not match the transaction.")


async def _process_crypto_confirmation(
    db: AsyncSession,
    tx_id: int,
    tx_hash: str,
    confirmed_amount: Decimal,
) -> dict[str, str]:
    token, already_processed = await _reserve_crypto_webhook(tx_hash)
    if already_processed:
        return {"status": "ok", "message": "Already processed."}

    committed = False
    wallet_user_id: int | None = None
    transaction_id: int | None = None
    try:
        tx_result = await db.execute(select(Transaction).where(Transaction.id == tx_id))
        transaction = tx_result.scalars().first()
        if not transaction:
            raise HTTPException(status_code=400, detail="Transaction not found.")
        if transaction.status != TransactionStatus.PENDING:
            if (
                transaction.status == TransactionStatus.SUCCESS
                and transaction.reference_id == tx_hash
            ):
                return {"status": "ok", "message": "Already processed."}
            raise HTTPException(status_code=409, detail="Transaction is not pending.")
        _validate_pending_crypto_transaction(transaction, confirmed_amount)

        # Resolve the exchange rate before any row lock is held.
        rate = Decimal(str(await get_usdt_rate()))
        if rate <= 0:
            raise HTTPException(status_code=503, detail="Exchange rate is unavailable.")

        wallet_result = await db.execute(
            select(Wallet).where(Wallet.id == transaction.wallet_id).with_for_update()
        )
        wallet = wallet_result.scalars().first()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found.")

        locked_tx_result = await db.execute(
            select(Transaction).where(Transaction.id == tx_id).with_for_update()
        )
        locked_tx = locked_tx_result.scalars().first()
        if not locked_tx:
            raise HTTPException(status_code=400, detail="Transaction not found.")
        if locked_tx.status != TransactionStatus.PENDING:
            if locked_tx.status == TransactionStatus.SUCCESS and locked_tx.reference_id == tx_hash:
                await db.rollback()
                return {"status": "ok", "message": "Already processed."}
            raise HTTPException(status_code=409, detail="Transaction is not pending.")
        _validate_pending_crypto_transaction(locked_tx, confirmed_amount)

        duplicate_result = await db.execute(
            select(Transaction.id).where(
                Transaction.id != locked_tx.id,
                Transaction.reference_id == tx_hash,
                Transaction.status == TransactionStatus.SUCCESS,
            )
        )
        if duplicate_result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=409, detail="Blockchain transaction was already used.")

        credit = to_decimal(Decimal(locked_tx.amount) * rate)
        wallet.balance = to_decimal(wallet.balance) + credit
        locked_tx.status = TransactionStatus.SUCCESS
        locked_tx.reference_id = tx_hash
        locked_tx.description = (
            f"USDT deposit confirmed: {confirmed_amount} USDT at {int(rate):,} T/USDT"
        )
        wallet_user_id = wallet.user_id
        transaction_id = locked_tx.id
        await db.commit()
        committed = True
        await _mark_crypto_webhook_processed(tx_hash)
    except HTTPException:
        if not committed:
            await db.rollback()
        raise
    except Exception as exc:
        if not committed:
            await db.rollback()
        logger.exception("Crypto webhook processing failed for transaction %d", tx_id)
        raise HTTPException(status_code=500, detail="Crypto webhook processing failed.") from exc
    finally:
        await _release_crypto_webhook(tx_hash, token)

    if wallet_user_id is not None and transaction_id is not None:
        try:
            user_result = await db.execute(select(User).where(User.id == wallet_user_id))
            user = user_result.scalars().first()
            if user:
                await _try_auto_purchase(db=db, user=user, tx_id=transaction_id)
        except Exception:
            logger.exception("Post-deposit purchase check failed for transaction %d", transaction_id)

    return {"status": "ok", "message": "Crypto deposit confirmed and wallet credited."}


class CryptoDepositRequest(BaseModel):
    amount_usdt: Decimal = Field(
        gt=Decimal("0"),
        max_digits=24,
        decimal_places=6,
        description="Expected USDT amount",
    )
    product_id: str | None = Field(default=None, max_length=120)
    variant_id: str | None = Field(default=None, max_length=120)


@router.get("/crypto/rate")
async def get_crypto_rate(user: User = Depends(current_user)):
    """Live USDT rate for the deposit UI to display the equivalent value."""
    rate = await get_usdt_rate()
    return {"tomanPerUsdt": int(rate), "base": "USDT", "quote": "تومان"}


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
    rate_limit = await check_rate_limit(
        "payment-crypto",
        user.telegram_id,
        limit=10,
        window_seconds=60,
    )
    if not rate_limit.allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded.")

    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found.")

    deposit_address = _usdt_trc20_deposit_address()
    expected_amount = _usdt_amount(payload.amount_usdt)
    pending_tx = Transaction(
        wallet_id=wallet.id,
        amount=expected_amount,
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

    await _store_purchase_intent(
        pending_tx.id,
        payload.product_id,
        payload.variant_id,
    )

    return {
        "status": "pending",
        "transactionId": pending_tx.id,
        "depositAddress": deposit_address,
        "network": "TRC20",
        "expectedAmount": str(expected_amount),
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

    _require_production_webhook_secret(settings.CRYPTO_WEBHOOK_SECRET, "Crypto")
    if settings.CRYPTO_WEBHOOK_SECRET:
        received_sig = request.headers.get("X-Crypto-Signature", "")
        if not _verify_hmac_signature(settings.CRYPTO_WEBHOOK_SECRET, raw_body, received_sig):
            logger.warning("Crypto webhook signature validation failed.")
            raise HTTPException(status_code=403, detail="Invalid webhook signature.")

    try:
        data = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.") from exc

    tx_id = data.get("transaction_id")
    tx_hash = str(data.get("tx_hash", "")).strip()
    amount_usdt = data.get("amount_usdt", "0")
    webhook_status = data.get("status", "")

    if webhook_status != "confirmed" or not tx_id or not tx_hash:
        return {"status": "ignored", "message": "Non-confirmed event skipped."}

    if not re.fullmatch(r"[A-Za-z0-9:_-]{8,200}", tx_hash):
        raise HTTPException(status_code=400, detail="Invalid tx_hash in payload.")

    # Validate identifiers before touching Redis/DB so malformed payloads fail cleanly
    try:
        tx_id_int = int(tx_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid transaction_id in payload.")

    confirmed_amount = _usdt_amount(amount_usdt)

    return await _process_crypto_confirmation(
        db=db,
        tx_id=tx_id_int,
        tx_hash=tx_hash,
        confirmed_amount=confirmed_amount,
    )
