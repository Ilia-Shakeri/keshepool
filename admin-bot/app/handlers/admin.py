from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart

from app.core.security import IsAdminFilter
from app.services.scheduler import send_hourly_report
from app.locales.translations import get_text

# Initialize router and enforce stealth middleware on all incoming data
admin_router = Router()
admin_router.message.filter(IsAdminFilter())
admin_router.callback_query.filter(IsAdminFilter())

# Configure default language metric
DEFAULT_LANG = "fa"

def get_main_menu_markup() -> InlineKeyboardMarkup:
    """Constructs the primary navigation keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Users", callback_data="manage_users"),
                InlineKeyboardButton(text="📦 Inventory", callback_data="manage_inventory")
            ],
            [
                InlineKeyboardButton(text="🎫 Tickets", callback_data="manage_tickets"),
                InlineKeyboardButton(text="📊 Push Report", callback_data="force_report")
            ]
        ]
    )

@admin_router.message(CommandStart())
async def cmd_start(message: Message):
    """Entrypoint for the bot. Renders the main dashboard."""
    await message.answer(
        text=get_text(DEFAULT_LANG, "main_menu"),
        reply_markup=get_main_menu_markup(),
        parse_mode="Markdown"
    )

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