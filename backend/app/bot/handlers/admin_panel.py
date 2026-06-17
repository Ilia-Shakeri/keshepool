from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func

from app.bot.filters import IsAdminFilter
from app.core.redis import redis_client
from app.core.database import AsyncSessionLocal
from app.models import User
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
                InlineKeyboardButton(text=get_text(lang, "users_title"), callback_data="manage_users_0"),
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

@admin_router.callback_query(F.data.startswith("manage_users"))
async def process_manage_users(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    
    # Extract page number from callback data (e.g., "manage_users_0")
    parts = callback.data.split("_")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    
    async with AsyncSessionLocal() as session:
        # Retrieve the total count for pagination context
        total_users = await session.scalar(select(func.count(User.id))) or 0
        
        # Execute query with strict pagination and eager loading to prevent N+1 issues
        result = await session.execute(
            select(User)
            .options(selectinload(User.wallet))
            .order_by(User.id.desc())
            .limit(10)
            .offset(page * 10)
        )
        users = result.scalars().all()

    # Compile the text response
    text = f"{get_text(lang, 'users_title')}\n\nTotal Users: {total_users}\n"
    for u in users:
        balance = float(u.wallet.balance) if u.wallet else 0.0
        text += f"• ID: {u.id} | @{u.username or 'N/A'} | Balance: {balance}\n"
        
    # Construct the pagination controls
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"manage_users_{page - 1}"))
    if (page + 1) * 10 < total_users:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"manage_users_{page + 1}"))
        
    keyboard = []
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="main_menu")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(text=text, reply_markup=markup)
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