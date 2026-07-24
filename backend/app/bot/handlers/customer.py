from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.core.config import settings

customer_router = Router()
customer_router.message.filter(F.chat.type == ChatType.PRIVATE)


@customer_router.message(CommandStart())
async def customer_start(message: Message) -> None:
    language = (message.from_user.language_code or "").lower()
    is_persian = language.startswith("fa")
    text = (
        "به کش‌پول خوش آمدید. برای مشاهده محصولات و حساب کاربری، مینی‌اپ را باز کنید."
        if is_persian
        else "Welcome to Keshepool. Open the Mini App to browse products and manage your account."
    )
    button_text = "باز کردن کش‌پول" if is_persian else "Open Keshepool"
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=button_text,
                        web_app=WebAppInfo(url=settings.WEB_APP_URL),
                    )
                ]
            ]
        ),
    )
