from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from app.core.security import IsAdminFilter
from app.services.scheduler import send_hourly_report
from app.locales.translations import get_text

admin_router = Router()
admin_router.message.filter(IsAdminFilter())
admin_router.callback_query.filter(IsAdminFilter())

# In-memory dictionary to maintain language state per admin user context
admin_language_state = {}

def get_main_menu_markup(lang: str) -> InlineKeyboardMarkup:
    """Constructs the primary navigation keyboard with localized context."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Users", callback_data="manage_users"),
                InlineKeyboardButton(text="📦 Inventory", callback_data="manage_inventory")
            ],
            [
                InlineKeyboardButton(text="🎫 Tickets", callback_data="manage_tickets"),
                InlineKeyboardButton(text="📊 Push Report", callback_data="force_report")
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "toggle_lang"), callback_data="toggle_language")
            ]
        ]
    )

@admin_router.message(CommandStart())
async def cmd_start(message: Message):
    lang = admin_language_state.get(message.from_user.id, "fa")
    await message.answer(
        text=get_text(lang, "main_menu"),
        reply_markup=get_main_menu_markup(lang),
        parse_mode="Markdown"
    )

@admin_router.callback_query(F.data == "toggle_language")
async def process_toggle_language(callback: CallbackQuery):
    """Mutates the localization state for the execution context."""
    current_lang = admin_language_state.get(callback.from_user.id, "fa")
    new_lang = "en" if current_lang == "fa" else "fa"
    admin_language_state[callback.from_user.id] = new_lang
    
    await callback.message.edit_text(
        text=get_text(new_lang, "main_menu"),
        reply_markup=get_main_menu_markup(new_lang),
        parse_mode="Markdown"
    )
    await callback.answer()

@admin_router.callback_query(F.data == "manage_users")
async def process_manage_users(callback: CallbackQuery):
    """Routes to the User Management dashboard."""
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(DEFAULT_LANG, "back"), callback_data="main_menu")]
        ]
    )
    await callback.message.edit_text(
        text=f"{get_text(DEFAULT_LANG, 'users_title')}\n\nAwaiting specific user query logic...",
        reply_markup=markup
    )
    await callback.answer()

@admin_router.callback_query(F.data == "manage_inventory")
async def process_manage_inventory(callback: CallbackQuery):
    """Routes to the Inventory Management dashboard."""
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(DEFAULT_LANG, "back"), callback_data="main_menu")]
        ]
    )
    await callback.message.edit_text(
        text=f"{get_text(DEFAULT_LANG, 'inventory_title')}\n\nAwaiting inventory ingestion logic...",
        reply_markup=markup
    )
    await callback.answer()

@admin_router.callback_query(F.data == "force_report")
async def process_force_report(callback: CallbackQuery):
    """Executes an immediate manual trigger of the APScheduler reporting function."""
    await send_hourly_report(callback.bot)
    
    # Show an interactive alert popup to the admin confirming execution
    await callback.answer(
        text=get_text(DEFAULT_LANG, "report_generated"),
        show_alert=True
    )

@admin_router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery):
    """Handles the return navigation to the root dashboard."""
    await callback.message.edit_text(
        text=get_text(DEFAULT_LANG, "main_menu"),
        reply_markup=get_main_menu_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()