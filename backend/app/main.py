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

if not settings.BOT_TOKEN or not settings.WEBHOOK_URL:
    module_logger.critical("Critical environment variables are missing.")
    sys.exit(1)

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

dp.include_router(admin_router)
dp.include_router(products_router)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.ASSET_ROOT).mkdir(parents=True, exist_ok=True)
    await init_db()
    
    scheduler = start_scheduler(bot)
    
    full_webhook_url = f"{settings.WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    module_logger.info("Setting Telegram webhook to %s", full_webhook_url)
    
    await bot.set_webhook(
        url=full_webhook_url, 
        drop_pending_updates=True,
        secret_token=settings.WEBHOOK_SECRET
    )
    
    try:
        yield
    finally:
        scheduler.shutdown()
        await redis_client.aclose()
        await bot.delete_webhook()
        await bot.session.close()

app = FastAPI(title="Keshepool API", lifespan=lifespan)

app.include_router(users.router)
app.include_router(products.router)
app.include_router(payments.router)
app.include_router(admin.router)

app.mount("/static", StaticFiles(directory=settings.ASSET_ROOT), name="static")

@app.get("/api/config")
async def get_public_config():
    return {"botUsername": settings.BOT_USERNAME}

@app.post(WEBHOOK_PATH)
async def bot_webhook(
    request: Request, 
    x_telegram_bot_api_secret_token: str = Header(None, alias="X-Telegram-Bot-Api-Secret-Token")
):
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        module_logger.warning("Unauthorized webhook payload received.")
        raise HTTPException(status_code=401, detail="Invalid secret token.")

    try:
        update_data = await request.json()
        telegram_update = types.Update(**update_data)
        await dp.feed_update(bot=bot, update=telegram_update)
        return {"status": "ok"}
    except Exception as exc:
        module_logger.exception("Webhook payload processing failed.")
        raise HTTPException(status_code=400, detail="Invalid webhook payload.") from exc

@app.get("/health")
async def health_check():
    return {"status": "healthy"}