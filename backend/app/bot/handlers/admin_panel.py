from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from app.bot.filters import IsAdminFilter
from app.core.redis import redis_client
from app.bot.services.scheduler import send_hourly_report
from app.bot.locales.translations import get_text

admin_router = Router()
admin_router.message.filter(IsAdminFilter())
admin_router.callback_query.filter(IsAdminFilter())

async def get_admin_lang(user_id: int) -> str:
    lang = await redis_client.get(f"admin_lang:{user_id}")
    return lang or "fa"

def get_main_menu_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, "users_title"), callback_data="manage_users"),
                InlineKeyboardButton(text=get_text(lang, "inventory_title"), callback_data="manage_inventory")
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "tickets_title"), callback_data="manage_tickets"),
                InlineKeyboardButton(text="📊 Push Report", callback_data="force_report")
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "toggle_lang"), callback_data="toggle_language")
            ]
        ]
    )

@admin_router.message(CommandStart())
async def cmd_start(message: Message):
    lang = await get_admin_lang(message.from_user.id)
    await message.answer(
        text=get_text(lang, "main_menu"),
        reply_markup=get_main_menu_markup(lang),
        parse_mode="Markdown"
    )

@admin_router.callback_query(F.data == "toggle_language")
async def process_toggle_language(callback: CallbackQuery):
    current_lang = await get_admin_lang(callback.from_user.id)
    new_lang = "en" if current_lang == "fa" else "fa"
    await redis_client.set(f"admin_lang:{callback.from_user.id}", new_lang)
    
    await callback.message.edit_text(
        text=get_text(new_lang, "main_menu"),
        reply_markup=get_main_menu_markup(new_lang),
        parse_mode="Markdown"
    )
    await callback.answer()

@admin_router.callback_query(F.data == "manage_users")
async def process_manage_users(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="main_menu")]
        ]
    )
    await callback.message.edit_text(
        text=f"{get_text(lang, 'users_title')}\n\nAwaiting specific user query logic...",
        reply_markup=markup
    )
    await callback.answer()

@admin_router.callback_query(F.data == "force_report")
async def process_force_report(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    await send_hourly_report(callback.bot)
    await callback.answer(
        text=get_text(lang, "report_generated"),
        show_alert=True
    )

@admin_router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    await callback.message.edit_text(
        text=get_text(lang, "main_menu"),
        reply_markup=get_main_menu_markup(lang),
        parse_mode="Markdown"
    )
    await callback.answer()