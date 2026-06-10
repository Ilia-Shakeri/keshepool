import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

# Initialize logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch environment variables safely
BOT_TOKEN = os.getenv("BOT_TOKEN", "fallback_token")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com")
WEBHOOK_PATH = "/webhook"

# Initialize Aiogram bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """
    Handles the /start command.
    Sends a welcome message and an inline button to open the Telegram Mini App.
    """
    web_app_url = "https://your-domain.com" 
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Open ZoodSub 🚀", 
                    web_app=WebAppInfo(url=web_app_url)
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
    TODO: Add database connection pool initialization here.
    """
    full_webhook_url = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    logger.info(f"Setting up webhook at: {full_webhook_url}")
    
    await bot.set_webhook(url=full_webhook_url)
    
    yield  # Application is running
    
    logger.info("Removing webhook and cleaning up resources...")
    await bot.delete_webhook()
    await bot.session.close()
    # TODO: Add database connection pool teardown here.

# Initialize FastAPI application
app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    """
    Endpoint that receives updates from Telegram servers.
    Validates payload and feeds it to the Aiogram dispatcher.
    """
    try:
        update_data = await request.json()
        telegram_update = types.Update(**update_data)
        await dp.feed_update(bot=bot, update=telegram_update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        raise HTTPException(status_code=400, detail="Invalid update payload")

@app.get("/health")
async def health_check():
    """
    Health check endpoint to verify the API is responsive.
    """
    return {"status": "healthy"}