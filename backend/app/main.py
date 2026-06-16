# ==================================================
# FILE: backend/app/main.py
# ==================================================

import os
import sys
import logging
import httpx
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

from app.core.database import get_db, AsyncSessionLocal
from app.models import Transaction, TransactionType, Wallet, User
from app.services.wallet_service import process_wallet_transaction
from app.core.security import validate_telegram_data

from app.api import admin, products  # Import the new routers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-domain.com")
WEBHOOK_PATH = "/webhook"

if not BOT_TOKEN or not WEBHOOK_URL:
    logger.critical("Critical environment variables missing. Terminating context.")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """
    Persists user to the database upon initialization of the bot context.
    """
    async with AsyncSessionLocal() as session:
        user_id_str = str(message.from_user.id)
        result = await session.execute(select(User).filter(User.telegram_id == user_id_str))
        user = result.scalars().first()
        
        if not user:
            new_user = User(telegram_id=user_id_str, role="user")
            session.add(new_user)
            await session.flush()
            
            new_wallet = Wallet(user_id=new_user.id, balance=0.00)
            session.add(new_wallet)
            await session.commit()
            logger.info(f"Registered new user in database: {user_id_str}")

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open Keshepool 🚀", 
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            ]
        ]
    )
    
    await message.answer(
        text="Welcome to Keshepool! Click the button below to access premium services.",
        reply_markup=markup
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    logger.info(f"Setting up webhook at: {full_webhook_url}")
    await bot.set_webhook(url=full_webhook_url)
    yield
    await bot.delete_webhook()
    await bot.session.close()

app = FastAPI(lifespan=lifespan)

# Register routers
app.include_router(admin.router)
app.include_router(products.router)

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    try:
        update_data = await request.json()
        telegram_update = types.Update(**update_data)
        await dp.feed_update(bot=bot, update=telegram_update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook payload error: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify infrastructure execution layer is responsive.
    """
    return {"status": "healthy"}

@app.get("/api/wallet/balance")
async def get_wallet_balance(telegram_data: dict = Depends(validate_telegram_data), db: AsyncSession = Depends(get_db)):
    """
    Retrieves the current wallet balance for the authenticated Telegram user.
    Secured by the validate_telegram_data middleware.
    """
    try:
        user_info = json.loads(telegram_data.get('user', '{}'))
        telegram_id = str(user_info.get('id'))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user payload structure")

    # Fetch the user using their unique telegram ID
    result = await db.execute(select(User).filter(User.telegram_id == telegram_id))
    user = result.scalars().first()

    # If the user has not interacted with the bot yet, default to 0
    if not user:
        return {"balance": 0}

    # Fetch the associated wallet
    wallet_result = await db.execute(select(Wallet).filter(Wallet.user_id == user.id))
    wallet = wallet_result.scalars().first()

    return {"balance": float(wallet.balance) if wallet else 0}

@app.post("/api/pay/tetra98")
async def create_tetra98_payment(amount: int, user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Initiates an IRR payment request to the Tetra98 API.
    Secures the flow by creating a pending transaction in the database BEFORE calling the gateway.
    """
    logger.info(f"Generating Tetra98 IRR payment for amount: {amount} for user: {user_id}")
    
    # Verify the user wallet exists
    result = await db.execute(select(Wallet).filter(Wallet.user_id == user_id))
    wallet = result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")

    # Create a pending transaction record to track the gateway state
    pending_tx = Transaction(
        wallet_id=wallet.id,
        amount=amount,
        type=TransactionType.DEPOSIT_IRR,
        reference_id="pending" 
    )
    db.add(pending_tx)
    await db.commit()
    await db.refresh(pending_tx)

    # Payload structure mapped for a standard gateway token request
    payload = {
        "api_key": TETRA98_API_KEY,
        "amount": amount,
        "callback_url": CALLBACK_URL,
        "description": f"Wallet charge for Keshepool user {user_id}",
        "order_id": pending_tx.id
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{TETRA98_API_URL}/request", json=payload, timeout=10.0)
            response_data = response.json()

            # Ensure the gateway responded positively
            if response.status_code == 200 and response_data.get("status") == "success":
                payment_link = response_data.get("payment_url")
                
                # Update transaction with authority reference if provided by gateway
                authority = response_data.get("authority")
                if authority:
                    pending_tx.reference_id = f"pending_{authority}"
                    await db.commit()

                return {
                    "status": "success",
                    "payment_url": payment_link,
                    "currency": "IRR"
                }
            else:
                logger.error(f"Tetra98 API error: {response_data}")
                pending_tx.reference_id = "failed"
                await db.commit()
                raise HTTPException(status_code=400, detail="Failed to initialize payment with Tetra98")

    except Exception as e:
        logger.error(f"HTTP Request failed for Tetra98: {e}")
        raise HTTPException(status_code=500, detail="Internal Gateway Error")

@app.post("/api/pay/tetra98/callback")
async def tetra98_payment_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handles the callback from Tetra98 after a user completes a payment.
    Verifies the gateway amount against the database record before executing the charge.
    """
    try:
        data = await request.json()
    except Exception:
        form_data = await request.form()
        data = dict(form_data)
        
    logger.info(f"Received callback from Tetra98: {data}")
    
    transaction_id = data.get("trans_id")
    status = data.get("status")
    order_id = data.get("order_id")
    
    if status == "success" and order_id:
        # Fetch the pending transaction using the order ID
        result = await db.execute(select(Transaction).filter(Transaction.id == int(order_id)))
        pending_tx = result.scalars().first()
        
        if not pending_tx or "pending" not in (pending_tx.reference_id or ""):
            raise HTTPException(status_code=400, detail="Invalid or already processed transaction")

        verify_payload = {
            "api_key": TETRA98_API_KEY,
            "trans_id": transaction_id
        }
        
        try:
            async with httpx.AsyncClient() as client:
                verify_res = await client.post(f"{TETRA98_API_URL}/verify", json=verify_payload, timeout=10.0)
                verify_data = verify_res.json()
                
                if verify_data.get("status") == "verified":
                    gateway_amount = verify_data.get("amount")
                    
                    # Verify the amount securely matches the local database record to prevent tampering
                    if float(gateway_amount) != float(pending_tx.amount):
                        logger.error("Payment amount mismatch detected during callback.")
                        raise HTTPException(status_code=400, detail="Payment amount mismatch")
                    
                    # Fetch wallet user_id for the transaction processor
                    wallet_res = await db.execute(select(Wallet).filter(Wallet.id == pending_tx.wallet_id))
                    wallet = wallet_res.scalars().first()

                    # Process the actual wallet top-up securely
                    await process_wallet_transaction(
                        db=db,
                        user_id=wallet.user_id,
                        amount=float(pending_tx.amount),
                        tx_type=TransactionType.DEPOSIT_IRR,
                        ref_id=transaction_id
                    )
                    
                    # Lock in the completed transaction state
                    pending_tx.reference_id = transaction_id
                    await db.commit()
                    
                    return {"status": "ok", "message": "Payment verified and wallet charged"}
                else:
                    logger.warning(f"Payment verification failed for transaction {transaction_id}")
                    raise HTTPException(status_code=400, detail="Payment verification failed")
        except Exception as e:
             logger.error(f"Verification request failed: {e}")
             raise HTTPException(status_code=500, detail="Verification error")
             
    return {"status": "failed", "message": "Payment was not successful"}