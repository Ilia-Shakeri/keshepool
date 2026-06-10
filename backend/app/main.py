import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

# Initialize logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch environment variables safely and assert execution constraints
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://your-domain.com")
WEBHOOK_PATH = "/webhook"

if not BOT_TOKEN or BOT_TOKEN == "fallback_token":
    logger.critical("BOT_TOKEN environment variable is missing or default! Terminating boot context.")
    sys.exit(1)

if not WEBHOOK_URL:
    logger.critical("WEBHOOK_URL environment variable is missing! Terminating boot context.")
    sys.exit(1)

# Initialize Aiogram bot and dispatcher securely
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """
    Handles the /start command.
    Sends a welcome message and an inline button to open the Telegram Mini App via environment configuration.
    """
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open ZoodSub 🚀", 
                    web_app=WebAppInfo(url=WEB_APP_URL)
                )
            ]
        ]
    )
    
    await message.answer(
        text="Welcome to ZoodSub! Click the button below to buy premium accounts.",
        reply_markup=markup
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the lifecycle of the FastAPI application.
    Initializes webhook on startup and cleans up resources on shutdown.
    """
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    logger.info(f"Setting up webhook at: {full_webhook_url}")
    
    await bot.set_webhook(url=full_webhook_url)
    
    yield  # Application engine running context
    
    logger.info("Removing webhook and cleaning up resources...")
    await bot.delete_webhook()
    await bot.session.close()

# Initialize FastAPI application
app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    """
    Endpoint that receives updates from Telegram servers.
    Validates payload structure and logs exceptions accurately without crashing.
    """
    try:
        update_data = await request.json()
        telegram_update = types.Update(**update_data)
        await dp.feed_update(bot=bot, update=telegram_update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook update payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid update payload structure")

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify infrastructure execution layer is responsive.
    """
    return {"status": "healthy"}