from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import IsAdminFilter
from app.database.session import AsyncSessionLocal
from app.states import ProductAdminStates
from app.locales.translations import get_text
from app.handlers.admin import admin_language_state

# Ensure absolute compliance with the security middleware
products_router = Router()
products_router.message.filter(IsAdminFilter())
products_router.callback_query.filter(IsAdminFilter())

@products_router.callback_query(F.data == "manage_inventory")
async def trigger_product_management(callback: CallbackQuery, state: FSMContext):
    """
    Fetches all active products from the shared database and presents them to the admin.
    """
    lang = admin_language_state.get(callback.from_user.id, "fa")
    
    async with AsyncSessionLocal() as session:
        from app.database.models import Product
        
        result = await session.execute(select(Product))
        products = result.scalars().all()

    keyboard = []
    # Build a button for every product found in the shared backend table
    for product in products:
        keyboard.append([InlineKeyboardButton(text=f"📦 {product.brand}", callback_data=f"edit_prod_{product.id}")])
    
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text=get_text(lang, "product_mgmt_title"),
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await state.set_state(ProductAdminStates.selecting_product)
    await callback.answer()

@products_router.callback_query(F.data.startswith("edit_prod_"), ProductAdminStates.selecting_product)
async def select_product_action(callback: CallbackQuery, state: FSMContext):
    """
    Presents the CRUD options for a specific product context.
    """
    lang = admin_language_state.get(callback.from_user.id, "fa")
    product_id = callback.data.split("edit_prod_")[1]
    
    # Persist the selected target in the FSM memory buffer
    await state.update_data(target_product_id=product_id)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, "edit_title"), callback_data="action_edit_name"),
                InlineKeyboardButton(text=get_text(lang, "edit_price"), callback_data="action_edit_price")
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "add_stock"), callback_data="action_add_stock")
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")
            ]
        ]
    )

    await callback.message.edit_text(
        text=f"{get_text(lang, 'config_product')} [{product_id}]\n{get_text(lang, 'select_action')}",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    await state.set_state(ProductAdminStates.selecting_action)
    await callback.answer()

@products_router.callback_query(F.data == "action_edit_price", ProductAdminStates.selecting_action)
async def prompt_new_price(callback: CallbackQuery, state: FSMContext):
    """
    Transitions state to await standard text input for the new price.
    """
    lang = admin_language_state.get(callback.from_user.id, "fa")
    await callback.message.answer(get_text(lang, "enter_new_price"))
    await state.set_state(ProductAdminStates.awaiting_new_price)
    await callback.answer()

@products_router.message(ProductAdminStates.awaiting_new_price)
async def process_new_price(message: Message, state: FSMContext):
    """
    Executes the database update for the product pricing payload.
    """
    lang = admin_language_state.get(message.from_user.id, "fa")
    
    try:
        new_price = float(message.text.strip())
    except ValueError:
        await message.answer(get_text(lang, "invalid_format"))
        return

    data = await state.get_data()
    product_id = data.get("target_product_id")

    async with AsyncSessionLocal() as session:
        from app.database.models import ProductVariant
        
        # Update the base variant logic (can be expanded later to target specific duration variants)
        result = await session.execute(select(ProductVariant).filter(ProductVariant.product_id == product_id))
        variant = result.scalars().first()
        
        if variant:
            variant.raw_price = new_price
            # Standard formatting logic - ensures UI reads cleanly
            variant.price_label = f"{int(new_price):,}" 
            await session.commit()
            
            success_msg = get_text(lang, "price_updated").replace("{price}", variant.price_label)
            await message.answer(success_msg)
        else:
            await message.answer(get_text(lang, "not_found"))

    # Flush state buffer upon completion
    await state.clear()