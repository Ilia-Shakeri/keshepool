from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import IsAdminFilter
from app.database.session import AsyncSessionLocal
from app.states import ProductAdminStates

# Ensure absolute compliance with the security middleware
products_router = Router()
products_router.message.filter(IsAdminFilter())
products_router.callback_query.filter(IsAdminFilter())

@products_router.callback_query(F.data == "manage_inventory")
async def trigger_product_management(callback: CallbackQuery, state: FSMContext):
    """
    Fetches all active products from the shared database and presents them to the admin.
    """
    async with AsyncSessionLocal() as session:
        # Note: We must mirror the Product model from the backend locally or execute raw queries
        # Assuming the backend Product model is synced to admin-bot/app/database/models.py
        from app.database.models import Product
        
        result = await session.execute(select(Product))
        products = result.scalars().all()

    keyboard = []
    for product in products:
        keyboard.append([InlineKeyboardButton(text=f"📦 {product.brand}", callback_data=f"edit_prod_{product.id}")])
    
    keyboard.append([InlineKeyboardButton(text="🔙 Back to Menu", callback_data="main_menu")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    await callback.message.edit_text(
        text="🛠 **Product Management**\nSelect a product to configure:",
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
    product_id = callback.data.split("edit_prod_")[1]
    
    # Persist the selected target in the FSM memory buffer
    await state.update_data(target_product_id=product_id)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Edit Title", callback_data="action_edit_name"),
                InlineKeyboardButton(text="💵 Update Price", callback_data="action_edit_price")
            ],
            [
                InlineKeyboardButton(text="📥 Add Stock", callback_data="action_add_stock")
            ],
            [
                InlineKeyboardButton(text="🔙 Back", callback_data="manage_inventory")
            ]
        ]
    )

    await callback.message.edit_text(
        text=f"⚙️ **Configuring Product [{product_id}]**\nSelect operation:",
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
    await callback.message.answer("Please reply with the new price in Toman (e.g., 250000):")
    await state.set_state(ProductAdminStates.awaiting_new_price)
    await callback.answer()

@products_router.message(ProductAdminStates.awaiting_new_price)
async def process_new_price(message: Message, state: FSMContext):
    """
    Executes the database update for the product pricing payload.
    """
    try:
        new_price = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Invalid format. Please enter numbers only.")
        return

    data = await state.get_data()
    product_id = data.get("target_product_id")

    async with AsyncSessionLocal() as session:
        from app.database.models import ProductVariant
        # Update the base variant logic (can be expanded to target specific variants)
        result = await session.execute(select(ProductVariant).filter(ProductVariant.product_id == product_id))
        variant = result.scalars().first()
        
        if variant:
            variant.raw_price = new_price
            # Standard formatting logic
            variant.price_label = f"{int(new_price):,}" 
            await session.commit()
            await message.answer(f"✅ Price successfully updated to {variant.price_label} Toman.")
        else:
            await message.answer("❌ Failed to locate product variant in database.")

    # Reset state
    await state.clear()