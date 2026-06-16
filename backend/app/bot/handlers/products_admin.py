import csv
import io
import re
import magic
import mimetypes
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.bot.filters import IsAdminFilter
from app.core.redis import redis_client
from app.core.database import AsyncSessionLocal
from app.models import Product, ProductVariant, InventoryItem, ItemStatus
from app.bot.locales.translations import get_text
from app.bot.states import ProductAdminStates

logger = logging.getLogger(__name__)

products_router = Router()
products_router.message.filter(IsAdminFilter())
products_router.callback_query.filter(IsAdminFilter())

ALLOWED_CATEGORIES = {"vpn", "music", "video", "ai", "social", "gaming", "tools", "edu", "finance"}
SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{2,120}$")

async def _lang(user_id: int) -> str:
    lang = await redis_client.get(f"admin_lang:{user_id}")
    return lang or "fa"

def _price_label(value: Decimal) -> str:
    return f"{int(value):,}"

def _validate_id(value: str, field: str) -> str:
    clean = value.strip()
    if not SAFE_ID_RE.match(clean):
        raise ValueError(f"{field} must contain only letters, numbers, underscores, or hyphens.")
    return clean

def parse_product_import(content: str) -> Tuple[List[Dict], List[str]]:
    rows: List[Dict] = []
    errors: List[str] = []
    reader = csv.reader(io.StringIO(content), delimiter="|")

    for index, row in enumerate(reader, start=1):
        if not row or not "".join(row).strip() or row[0].strip().startswith("#"):
            continue

        if len(row) < 8:
            errors.append(f"Line {index}: expected at least 8 pipe-separated columns.")
            continue

        try:
            product_id = _validate_id(row[0], "product_id")
            variant_id = _validate_id(row[5], "variant_id")
            category = row[4].strip() or "tools"
            if category not in ALLOWED_CATEGORIES:
                raise ValueError(f"category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}")

            raw_price = Decimal(row[7].strip())
            if raw_price <= 0:
                raise ValueError("raw_price must be positive.")

            credentials = []
            if len(row) >= 9 and row[8].strip():
                credentials = [item.strip() for item in row[8].split(";") if item.strip()]

            rows.append({
                "product_id": product_id,
                "title": row[1].strip(),
                "brand": row[2].strip(),
                "subtitle": row[3].strip(),
                "category": category,
                "variant_id": variant_id,
                "duration": row[6].strip(),
                "raw_price": float(raw_price),
                "credentials": credentials,
            })
        except (InvalidOperation, ValueError) as exc:
            errors.append(f"Line {index}: {exc}")

    return rows, errors

@products_router.callback_query(F.data == "manage_inventory")
async def trigger_product_management(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    keyboard = [
        [InlineKeyboardButton(text=get_text(lang, "bulk_import"), callback_data="bulk_import_products")]
    ]

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Product).order_by(Product.brand.asc())
            )
            products = result.scalars().all()

            for product in products:
                status = "✅" if product.is_active else "⛔"
                keyboard.append(
                    [InlineKeyboardButton(text=f"{status} {product.brand}", callback_data=f"edit_prod_{product.id}")]
                )
        except Exception as e:
            logger.error("DB Error fetching products: %s", e)
            await callback.answer(f"Database Error", show_alert=True)
            return

    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")])

    await callback.message.edit_text(
        text=get_text(lang, "product_mgmt_title"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown",
    )
    await state.set_state(ProductAdminStates.selecting_product)
    await callback.answer()

@products_router.callback_query(F.data.startswith("edit_prod_"), ProductAdminStates.selecting_product)
async def select_product_action(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    product_id = callback.data.removeprefix("edit_prod_")
    await state.update_data(target_product_id=product_id)

    async with AsyncSessionLocal() as session:
        try:
            product = await session.get(Product, product_id)
            if not product:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            
            stock_result = await session.execute(
                select(func.count(InventoryItem.id)).where(
                    InventoryItem.product_id == product.id,
                    InventoryItem.status == ItemStatus.AVAILABLE
                )
            )
            stock_count = stock_result.scalar() or 0
        except Exception as e:
            logger.error("DB Error fetching product variants: %s", e)
            await callback.answer("Database Error", show_alert=True)
            return

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, "edit_title"), callback_data="action_edit_name"),
                InlineKeyboardButton(text=get_text(lang, "edit_price"), callback_data="action_edit_price"),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "add_stock"), callback_data="action_add_stock"),
                InlineKeyboardButton(text=get_text(lang, "upload_logo"), callback_data="action_upload_logo"),
            ],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")],
        ]
    )

    await callback.message.edit_text(
        text=f"{get_text(lang, 'config_product')} [{product_id}]\n{get_text(lang, 'available_stock')}: {stock_count}",
        reply_markup=markup,
        parse_mode="Markdown",
    )
    await state.set_state(ProductAdminStates.selecting_action)
    await callback.answer()

@products_router.callback_query(F.data == "bulk_import_products")
async def prompt_bulk_import(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "bulk_import_help"))
    await state.set_state(ProductAdminStates.awaiting_bulk_import_file)
    await callback.answer()

@products_router.message(ProductAdminStates.awaiting_bulk_import_file, F.document)
async def process_bulk_import_file(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    document = message.document

    if not document.file_name.lower().endswith(".txt"):
        await message.answer(get_text(lang, "txt_required"))
        return

    buffer = io.BytesIO()
    await message.bot.download(document, destination=buffer)
    content = buffer.getvalue().decode("utf-8-sig", errors="replace")
    rows, errors = parse_product_import(content)

    if errors:
        await message.answer(get_text(lang, "bulk_import_errors") + "\n" + "\n".join(errors[:10]))
        return

    inserted_credentials = 0
    chunk_size = 50
    chunk_errors = []

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        async with AsyncSessionLocal() as session:
            try:
                for row in chunk:
                    product_id = row["product_id"]
                    variant_id = row["variant_id"]
                    
                    product = await session.get(Product, product_id)
                    if not product:
                        product = Product(
                            id=product_id,
                            title=row["title"],
                            brand=row["brand"],
                            subtitle=row["subtitle"],
                            category=row["category"],
                            is_active=True
                        )
                        session.add(product)
                    
                    variant = await session.get(ProductVariant, variant_id)
                    if not variant:
                        variant = ProductVariant(
                            id=variant_id,
                            product_id=product_id,
                            duration=row["duration"],
                            raw_price=row["raw_price"],
                            price_label=f"{int(row['raw_price']):,}",
                            is_active=True
                        )
                        session.add(variant)

                    if row["credentials"]:
                        for cred in row["credentials"]:
                            exists_result = await session.execute(
                                select(InventoryItem).where(
                                    InventoryItem.product_id == product_id,
                                    InventoryItem.variant_id == variant_id,
                                    InventoryItem.credentials == cred
                                )
                            )
                            
                            if not exists_result.scalars().first():
                                session.add(InventoryItem(
                                    product_id=product_id,
                                    variant_id=variant_id,
                                    credentials=cred,
                                    status=ItemStatus.AVAILABLE
                                ))
                                inserted_credentials += 1
                                
                await session.commit()
                
            except Exception as exc:
                await session.rollback()
                logger.error("Transaction rollback on data pipeline slice at index %d: %s", i, exc)
                chunk_errors.append(f"Chunk {i//chunk_size + 1} failed: {exc}")
                continue

    await redis_client.delete("cache:products:all")
    await state.clear()
    
    if chunk_errors:
        error_msg = get_text(lang, "bulk_import_errors") + "\n" + "\n".join(chunk_errors[:5])
        await message.answer(error_msg)
    else:
        await message.answer(
            get_text(lang, "bulk_import_success")
            .replace("{products}", str(len({row["product_id"] for row in rows})))
            .replace("{credentials}", str(inserted_credentials))
        )

@products_router.callback_query(F.data == "action_edit_price", ProductAdminStates.selecting_action)
async def prompt_new_price(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "enter_new_price"))
    await state.set_state(ProductAdminStates.awaiting_new_price)
    await callback.answer()

@products_router.message(ProductAdminStates.awaiting_new_price)
async def process_new_price(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    try:
        new_price = float(message.text.strip())
        if new_price <= 0:
            raise ValueError
    except Exception:
        await message.answer(get_text(lang, "invalid_format"))
        return

    data = await state.get_data()
    product_id = data.get("target_product_id")

    async with AsyncSessionLocal() as session:
        try:
            product = await session.get(Product, product_id)
            if not product:
                await message.answer(get_text(lang, "not_found"))
                return
            
            variants_result = await session.execute(
                select(ProductVariant)
                .where(ProductVariant.product_id == product_id, ProductVariant.is_active.is_(True))
                .with_for_update()
            )
            for variant in variants_result.scalars().all():
                variant.raw_price = new_price
                variant.price_label = f"{int(new_price):,}"
                
            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as e:
            await session.rollback()
            logger.error("DB Update Error: %s", e)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "price_updated").replace("{price}", _price_label(Decimal(new_price))))

@products_router.callback_query(F.data == "action_edit_name", ProductAdminStates.selecting_action)
async def prompt_new_name(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "enter_new_name"))
    await state.set_state(ProductAdminStates.awaiting_new_name)
    await callback.answer()

@products_router.message(ProductAdminStates.awaiting_new_name)
async def process_new_name(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    new_name = message.text.strip()
    if len(new_name) < 2 or len(new_name) > 180:
        await message.answer(get_text(lang, "invalid_format"))
        return

    data = await state.get_data()
    product_id = data.get("target_product_id")
    
    async with AsyncSessionLocal() as session:
        try:
            product = await session.get(Product, product_id)
            if not product:
                await message.answer(get_text(lang, "not_found"))
                return
            
            product.title = new_name
            product.brand = new_name
            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as e:
            await session.rollback()
            logger.error("DB Update Error: %s", e)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "name_updated"))

@products_router.callback_query(F.data == "action_add_stock", ProductAdminStates.selecting_action)
async def prompt_stock_text(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "enter_stock_lines"))
    await state.set_state(ProductAdminStates.awaiting_stock_text)
    await callback.answer()

@products_router.message(ProductAdminStates.awaiting_stock_text)
async def process_stock_text(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    credentials = [line.strip() for line in message.text.splitlines() if line.strip()]
    if not credentials:
        await message.answer(get_text(lang, "invalid_format"))
        return

    data = await state.get_data()
    product_id = data.get("target_product_id")
    inserted = 0

    async with AsyncSessionLocal() as session:
        try:
            product = await session.execute(
                select(Product).options(selectinload(Product.variants)).where(Product.id == product_id)
            )
            product = product.scalars().first()
            
            if not product or not product.variants:
                await message.answer(get_text(lang, "not_found"))
                return
                
            variant_id = product.variants[0].id
            
            for credential in credentials:
                exists_result = await session.execute(
                    select(InventoryItem).where(
                        InventoryItem.product_id == product_id,
                        InventoryItem.variant_id == variant_id,
                        InventoryItem.credentials == credential,
                    ).with_for_update()
                )
                
                if exists_result.scalars().first():
                    continue
                    
                session.add(
                    InventoryItem(
                        product_id=product_id,
                        variant_id=variant_id,
                        credentials=credential,
                        status=ItemStatus.AVAILABLE,
                    )
                )
                inserted += 1

            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as e:
            await session.rollback()
            logger.error("DB Insert Error: %s", e)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "stock_added").replace("{count}", str(inserted)))

@products_router.callback_query(F.data == "action_upload_logo", ProductAdminStates.selecting_action)
async def prompt_logo_upload(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "send_logo"))
    await state.set_state(ProductAdminStates.awaiting_logo_upload)
    await callback.answer()

@products_router.message(ProductAdminStates.awaiting_logo_upload)
async def process_logo_upload(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    product_id = data.get("target_product_id")

    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        if message.document.file_size and message.document.file_size > 2_000_000:
            await message.answer(get_text(lang, "logo_too_large"))
            return
        file_id = message.document.file_id

    if not file_id:
        await message.answer(get_text(lang, "image_required"))
        return

    buffer = io.BytesIO()
    await message.bot.download(file_id, destination=buffer)
    file_bytes = buffer.getvalue()

    mime_type = magic.from_buffer(file_bytes, mime=True)
    if not mime_type.startswith("image/"):
        await message.answer(get_text(lang, "image_required"))
        return

    extension = mimetypes.guess_extension(mime_type) or ".jpg"
    safe_product_id = re.sub(r"[^a-zA-Z0-9_-]", "_", product_id)
    
    asset_dir = Path(settings.ASSET_ROOT) / "product-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    target_path = asset_dir / f"{safe_product_id}{extension}"
    target_path.write_bytes(file_bytes)

    asset_url = f"{settings.PUBLIC_ASSET_BASE_URL.rstrip('/')}/product-assets/{target_path.name}"

    async with AsyncSessionLocal() as session:
        try:
            product = await session.get(Product, product_id)
            if not product:
                await message.answer(get_text(lang, "not_found"))
                return
            
            product.asset_url = asset_url
            product.icon = "Image"
            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as e:
            await session.rollback()
            logger.error("DB Update Error: %s", e)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "logo_uploaded"))