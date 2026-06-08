from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart
import os
import logging

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fetch environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "fallback_token")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-domain.com/webhook")
WEBHOOK_PATH = f"/webhook"

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def handle_start(message: types.Message):
    """
    Handles the /start command.
    Sends a welcome message and an inline button to open the Web App.
    """
    # URL to the Next.js frontend (we will set this up next)
    web_app_url = "https://your-future-frontend-url.com" 
    
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
    Sets the webhook on startup and removes it on shutdown.
    """
    logger.info("Setting up webhook...")
    await bot.set_webhook(url=f"{WEBHOOK_URL}{WEBHOOK_PATH}")
    yield
    logger.info("Removing webhook...")
    await bot.delete_webhook()
    await bot.session.close()

# Initialize FastAPI application
app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    """
    Endpoint that receives updates from Telegram servers.
    """
    update = await request.json()
    telegram_update = types.Update(**update)
    await dp.feed_update(bot=bot, update=telegram_update)
    return {"status": "ok"}

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint to verify the server is running.
    """
    return {"status": "healthy"}