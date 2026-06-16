import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.staticfiles import StaticFiles
from pythonjsonlogger import jsonlogger

from app.api import admin, payments, products, users
from app.bot.handlers.admin_panel import admin_router
from app.bot.handlers.products_admin import products_router
from app.bot.services.scheduler import start_scheduler
from app.core.config import settings
from app.core.database import init_db
from app.core.redis import redis_client

# Configure logging
logger = logging.getLogger()
if logger.handlers:
    logger.handlers.clear()
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

module_logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"

# Ensure critical environment variables exist
if not settings.BOT_TOKEN or not settings.ADMIN_BOT_TOKEN or not settings.WEBHOOK_URL:
    module_logger.critical("Critical environment variables (BOT_TOKEN/ADMIN_BOT_TOKEN/WEBHOOK_URL) are missing.")
    sys.exit(1)

# Initialize Main Bot (Mini-App)
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

# Initialize Admin Bot
admin_bot = Bot(token=settings.ADMIN_BOT_TOKEN)
admin_dp = Dispatcher()

# Register routers
admin_dp.include_router(admin_router)
admin_dp.include_router(products_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.ASSET_ROOT).mkdir(parents=True, exist_ok=True)
    await init_db()
    
    # Scheduler runs on the admin bot
    scheduler = start_scheduler(admin_bot)
    
    full_webhook_url = settings.WEBHOOK_URL.rstrip('/')
    module_logger.info("Setting Telegram webhooks...")
    
    await bot.set_webhook(
        url=f"{full_webhook_url}{WEBHOOK_PATH}/main", 
        drop_pending_updates=True,
        secret_token=settings.WEBHOOK_SECRET
    )
    await admin_bot.set_webhook(
        url=f"{full_webhook_url}{WEBHOOK_PATH}/admin", 
        drop_pending_updates=True,
        secret_token=settings.WEBHOOK_SECRET
    )
    
    try:
        yield
    finally:
        scheduler.shutdown()
        await redis_client.aclose()
        await bot.delete_webhook()
        await admin_bot.delete_webhook()
        await bot.session.close()
        await admin_bot.session.close()

app = FastAPI(title="Keshepool API", lifespan=lifespan)

app.include_router(users.router)
app.include_router(products.router)
app.include_router(payments.router)
app.include_router(admin.router)

app.mount("/static", StaticFiles(directory=settings.ASSET_ROOT), name="static")

@app.get("/api/config")
async def get_public_config():
    return {"botUsername": settings.BOT_USERNAME}

@app.post(f"{WEBHOOK_PATH}/{{bot_type}}")
async def bot_webhook(
    bot_type: str,
    request: Request, 
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        module_logger.warning("Unauthorized webhook payload received.")
        raise HTTPException(status_code=401, detail="Invalid secret token.")

    try:
        update_data = await request.json()
        telegram_update = types.Update(**update_data)
        
        if bot_type == "admin":
            await admin_dp.feed_update(bot=admin_bot, update=telegram_update)
        else:
            await dp.feed_update(bot=bot, update=telegram_update)
            
        return {"status": "ok"}
    except Exception as exc:
        module_logger.exception("Webhook payload processing failed.")
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

@app.get("/health")
async def health_check():
    return {"status": "healthy"}