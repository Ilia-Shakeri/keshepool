import csv
import hashlib
import html
import io
import json
import logging
import mimetypes
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Tuple

from aiogram import F, Router
from aiogram.filters import Command
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
MAX_FEATURES = 4


async def _lang(user_id: int) -> str:
    lang = await redis_client.get(f"admin_lang:{user_id}")
    return lang or "fa"


def _h(text: object) -> str:
    return html.escape(str(text) if text is not None else "")


def _price_label(value: Decimal) -> str:
    return f"{int(value):,}"


def _validate_id(value: str, field: str) -> str:
    clean = value.strip()
    if not SAFE_ID_RE.match(clean):
        raise ValueError(f"{field} must contain only letters, numbers, underscores, or hyphens.")
    return clean


def _brand_hash(brand: str) -> str:
    """12-char deterministic hex ID for a brand name — safe for callback_data."""
    return hashlib.md5(brand.encode()).hexdigest()[:12]


def _cancel_markup(lang: str) -> InlineKeyboardMarkup:
    label = "❌ لغو" if lang == "fa" else "❌ Cancel"
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data="cancel_input")]]
    )


# ── Product management navigation ─────────────────────────────────────────────

async def show_product_management_menu(target, lang: str, state: FSMContext, send_new: bool = False) -> None:
    """Show the three primary product management actions."""
    await state.clear()
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "add_single_product"), callback_data="add_single_product")],
            [InlineKeyboardButton(text=get_text(lang, "add_bulk_product"), callback_data="bulk_import_products")],
            [InlineKeyboardButton(text=get_text(lang, "view_products"), callback_data="view_products")],
        ]
    )
    text = get_text(lang, "product_mgmt_title")

    if send_new:
        await target.answer(text=text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")


async def show_brands(target, lang: str, state: FSMContext, send_new: bool = False) -> None:
    """Show unique product brands as grouped buttons for product editing."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Product.brand, func.count(Product.id).label("cnt"))
                .group_by(Product.brand)
                .order_by(Product.brand.asc())
            )
            brands_data = result.all()
    except Exception as exc:
        logger.error("DB error loading brands: %s", exc)
        err = get_text(lang, "db_error")
        if send_new:
            await target.answer(err)
        else:
            await target.message.answer(err)
        return

    keyboard: list[list[InlineKeyboardButton]] = []

    for brand, cnt in brands_data:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📦 {brand} ({cnt})",
                callback_data=f"sel_brand_{_brand_hash(brand)}",
            )
        ])

    if not keyboard:
        keyboard.append([InlineKeyboardButton(text=get_text(lang, "add_single_product"), callback_data="add_single_product")])

    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    text = get_text(lang, "products_list_title")
    if not brands_data:
        text += "\n\n" + get_text(lang, "product_list_empty")

    if send_new:
        await target.answer(text=text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")

    await state.set_state(ProductAdminStates.selecting_brand)


@products_router.callback_query(F.data == "manage_inventory")
async def trigger_product_management(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await show_product_management_menu(callback, lang, state)
    await callback.answer()


@products_router.callback_query(F.data == "view_products")
async def trigger_product_list(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await show_brands(callback, lang, state)
    await callback.answer()


@products_router.callback_query(F.data == "add_single_product")
async def prompt_single_product(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "single_product_help"), reply_markup=_cancel_markup(lang), parse_mode="HTML")
    await state.set_state(ProductAdminStates.awaiting_single_product_json)
    await callback.answer()


def _coerce_product_payload(raw: Any) -> Dict[str, Any]:
    """Validate and normalize one product payload from admin input."""
    if not isinstance(raw, dict):
        raise ValueError("Product payload must be a JSON object.")

    product_id = _validate_id(str(raw.get("id", "")), "id")
    title = str(raw.get("title", "")).strip()
    brand = str(raw.get("brand", "")).strip()
    category = str(raw.get("category", "tools")).strip() or "tools"
    variants = raw.get("variants")

    if not title or not brand:
        raise ValueError("title and brand are required.")
    if category not in ALLOWED_CATEGORIES:
        raise ValueError(f"category must be one of: {', '.join(sorted(ALLOWED_CATEGORIES))}")
    if not isinstance(variants, list) or not variants:
        raise ValueError("variants must be a non-empty array.")

    features = raw.get("features")
    if features is not None:
        if not isinstance(features, list):
            raise ValueError("features must be an array.")
        features = [str(feature).strip() for feature in features if str(feature).strip()][:MAX_FEATURES]

    normalized_variants = []
    for index, variant_raw in enumerate(variants, start=1):
        if not isinstance(variant_raw, dict):
            raise ValueError(f"variant {index} must be an object.")

        variant_id = _validate_id(str(variant_raw.get("id", "")), "variant_id")
        duration = str(variant_raw.get("duration", "")).strip()
        raw_price = Decimal(str(variant_raw.get("rawPrice", variant_raw.get("raw_price", ""))))
        if not duration or raw_price <= 0:
            raise ValueError(f"variant {index} requires duration and positive rawPrice.")

        credentials = variant_raw.get("credentials", [])
        if credentials is None:
            credentials = []
        if not isinstance(credentials, list):
            raise ValueError(f"variant {index} credentials must be an array.")

        normalized_variants.append(
            {
                "id": variant_id,
                "duration": duration,
                "raw_price": raw_price,
                "price_label": str(variant_raw.get("priceLabel") or _price_label(raw_price)),
                "credentials": [str(item).strip() for item in credentials if str(item).strip()],
            }
        )

    return {
        "id": product_id,
        "title": title,
        "brand": brand,
        "subtitle": str(raw.get("subtitle", "")).strip(),
        "icon": str(raw.get("icon", "Box") or "Box").strip(),
        "asset_url": raw.get("assetUrl"),
        "gradient": str(raw.get("gradient", "from-gray-700 to-black") or "from-gray-700 to-black").strip(),
        "category": category,
        "features": features,
        "variants": normalized_variants,
    }


async def _upsert_product_payload(session, payload: Dict[str, Any]) -> int:
    """Create or update one product, its variants, and optional inventory rows."""
    product = await session.get(Product, payload["id"])
    if not product:
        product = Product(id=payload["id"])
        session.add(product)

    product.title = payload["title"]
    product.brand = payload["brand"]
    product.subtitle = payload["subtitle"]
    product.icon = payload["icon"]
    product.asset_url = payload["asset_url"]
    product.gradient = payload["gradient"]
    product.category = payload["category"]
    product.features = json.dumps(payload["features"], ensure_ascii=False) if payload["features"] else None
    product.is_active = True

    inserted_credentials = 0
    for variant_payload in payload["variants"]:
        variant = await session.get(ProductVariant, variant_payload["id"])
        if not variant:
            variant = ProductVariant(id=variant_payload["id"], product_id=payload["id"])
            session.add(variant)

        variant.product_id = payload["id"]
        variant.duration = variant_payload["duration"]
        variant.raw_price = variant_payload["raw_price"]
        variant.price_label = variant_payload["price_label"]
        variant.is_active = True

        for credential in variant_payload["credentials"]:
            exists = await session.execute(
                select(InventoryItem).where(
                    InventoryItem.product_id == payload["id"],
                    InventoryItem.variant_id == variant_payload["id"],
                    InventoryItem.credentials == credential,
                )
            )
            if exists.scalars().first():
                continue

            session.add(
                InventoryItem(
                    product_id=payload["id"],
                    variant_id=variant_payload["id"],
                    credentials=credential,
                    status=ItemStatus.AVAILABLE,
                )
            )
            inserted_credentials += 1

    return inserted_credentials


@products_router.message(ProductAdminStates.awaiting_single_product_json)
async def process_single_product_json(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    try:
        payload = _coerce_product_payload(json.loads(message.text or ""))
    except (json.JSONDecodeError, InvalidOperation, ValueError) as exc:
        logger.warning("Single product payload rejected: %s", exc)
        await message.answer(get_text(lang, "single_product_invalid"))
        return

    try:
        async with AsyncSessionLocal() as session:
            await _upsert_product_payload(session, payload)
            await session.commit()
    except Exception as exc:
        logger.error("Single product upsert failed: %s", exc, exc_info=True)
        await message.answer(get_text(lang, "db_error"))
        return

    await redis_client.delete("cache:products:all")
    await state.clear()
    await message.answer(get_text(lang, "single_product_success"))


@products_router.callback_query(F.data.startswith("sel_brand_"))
async def handle_brand_selection(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    brand_hash_val = callback.data.removeprefix("sel_brand_")

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Product).order_by(Product.brand.asc(), Product.created_at.asc())
            )
            all_products = result.scalars().all()
    except Exception as exc:
        logger.error("DB error loading products for brand: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    # Identify the target brand via its deterministic hash
    target_brand: str | None = None
    seen: set[str] = set()
    for p in all_products:
        if p.brand not in seen:
            seen.add(p.brand)
            if _brand_hash(p.brand) == brand_hash_val:
                target_brand = p.brand
                break

    if not target_brand:
        await callback.answer(get_text(lang, "brand_not_found"), show_alert=True)
        return

    brand_products = [p for p in all_products if p.brand == target_brand]
    keyboard: list[list[InlineKeyboardButton]] = []

    for product in brand_products:
        icon = "✅" if product.is_active else "⛔"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon} {product.title} [{product.id}]",
                callback_data=f"edit_prod_{product.id}",
            )
        ])

    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")])

    await state.update_data(current_brand=target_brand)
    await callback.message.edit_text(
        text=f"📦 <b>{_h(target_brand)}</b>\n\n{get_text(lang, 'select_product_in_brand')}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )
    await state.set_state(ProductAdminStates.selecting_product)
    await callback.answer()


# ── Product action menu ───────────────────────────────────────────────────────

@products_router.callback_query(F.data.startswith("edit_prod_"))
async def select_product_action(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    product_id = callback.data.removeprefix("edit_prod_")
    await state.update_data(target_product_id=product_id)

    try:
        async with AsyncSessionLocal() as session:
            product = await session.get(Product, product_id)
            if not product:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            stock_count = await session.scalar(
                select(func.count(InventoryItem.id)).where(
                    InventoryItem.product_id == product.id,
                    InventoryItem.status == ItemStatus.AVAILABLE,
                )
            ) or 0
    except Exception as exc:
        logger.error("DB error in select_product_action: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    active_icon = "✅" if product.is_active else "⛔"
    toggle_label = get_text(lang, "toggle_product") + f" ({active_icon})"

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, "edit_title"), callback_data="action_edit_name"),
                InlineKeyboardButton(text=get_text(lang, "edit_price"), callback_data="action_edit_price"),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "edit_subtitle"), callback_data="action_edit_subtitle"),
                InlineKeyboardButton(text=get_text(lang, "edit_features"), callback_data="action_edit_features"),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "add_stock"), callback_data="action_add_stock"),
                InlineKeyboardButton(text=get_text(lang, "upload_logo"), callback_data="action_upload_logo"),
            ],
            [
                InlineKeyboardButton(text=toggle_label, callback_data="action_toggle_active"),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "delete_product"), callback_data="action_delete_product"),
            ],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")],
        ]
    )

    features_preview = ""
    if product.features:
        try:
            fl = json.loads(product.features)
            features_preview = "\n⭐ " + " | ".join(fl[:MAX_FEATURES])
        except Exception:
            pass

    text = (
        f"{get_text(lang, 'config_product')} <code>[{_h(product_id)}]</code>\n"
        f"📦 {get_text(lang, 'available_stock')}: <b>{stock_count}</b>"
        f"{_h(features_preview)}"
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await state.set_state(ProductAdminStates.selecting_action)
    await callback.answer()


# ── Toggle active ────────────────────────────────────────────────────────────

@products_router.callback_query(F.data == "action_toggle_active")
async def toggle_product_active(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    data = await state.get_data()
    product_id = data.get("target_product_id")

    try:
        async with AsyncSessionLocal() as session:
            product = await session.get(Product, product_id)
            if not product:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            product.is_active = not product.is_active
            await session.commit()
            await redis_client.delete("cache:products:all")
            new_state = product.is_active
    except Exception as exc:
        logger.error("Toggle active error: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    key = "product_activated" if new_state else "product_deactivated"
    await callback.answer(get_text(lang, key), show_alert=True)
    try:
        await select_product_action(callback, state)
    except Exception:
        # Message may no longer be editable; silently ignore
        pass


@products_router.callback_query(F.data == "action_delete_product")
async def prompt_delete_product(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "confirm_delete_yes"), callback_data="confirm_delete_product")],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")],
        ]
    )
    await callback.message.answer(get_text(lang, "confirm_delete_product"), reply_markup=markup)
    await callback.answer()


@products_router.callback_query(F.data == "confirm_delete_product")
async def soft_delete_product(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    data = await state.get_data()
    product_id = data.get("target_product_id")

    try:
        async with AsyncSessionLocal() as session:
            product = await session.get(Product, product_id)
            if not product:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            product.is_active = False
            variants_result = await session.execute(
                select(ProductVariant).where(ProductVariant.product_id == product_id).with_for_update()
            )
            for variant in variants_result.scalars().all():
                variant.is_active = False
            await session.commit()
    except Exception as exc:
        logger.error("Product delete failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    await redis_client.delete("cache:products:all")
    await state.clear()
    await callback.message.edit_text(get_text(lang, "product_deleted"))
    await callback.answer()


# ── Edit title ────────────────────────────────────────────────────────────────

@products_router.callback_query(F.data == "action_edit_name")
async def prompt_new_name(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "enter_new_name"), reply_markup=_cancel_markup(lang))
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
            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as exc:
            await session.rollback()
            logger.error("Name update error: %s", exc)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "name_updated"))


# ── Edit subtitle ─────────────────────────────────────────────────────────────

@products_router.callback_query(F.data == "action_edit_subtitle")
async def prompt_new_subtitle(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "enter_new_subtitle"), reply_markup=_cancel_markup(lang))
    await state.set_state(ProductAdminStates.awaiting_new_subtitle)
    await callback.answer()


@products_router.message(ProductAdminStates.awaiting_new_subtitle)
async def process_new_subtitle(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    new_subtitle = message.text.strip()
    if not new_subtitle or len(new_subtitle) > 500:
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
            product.subtitle = new_subtitle
            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as exc:
            await session.rollback()
            logger.error("Subtitle update error: %s", exc)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "subtitle_updated"))


# ── Edit features ─────────────────────────────────────────────────────────────

@products_router.callback_query(F.data == "action_edit_features")
async def prompt_new_features(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    data = await state.get_data()
    product_id = data.get("target_product_id")

    # Show current features so admin knows what to replace
    current_preview = ""
    try:
        async with AsyncSessionLocal() as session:
            product = await session.get(Product, product_id)
            if product and product.features:
                fl = json.loads(product.features)
                current_label = "Current" if lang == "en" else "فعلی"
                current_preview = f"\n\n{current_label}:\n" + "\n".join(f"  • {f}" for f in fl)
    except Exception:
        pass

    await callback.message.answer(
        get_text(lang, "enter_new_features") + _h(current_preview) + "\n\n" + get_text(lang, "cancel_hint"),
        parse_mode="HTML",
    )
    await state.set_state(ProductAdminStates.awaiting_new_features)
    await callback.answer()


@products_router.message(ProductAdminStates.awaiting_new_features)
async def process_new_features(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    raw_lines = [line.strip() for line in message.text.splitlines() if line.strip()]

    if not raw_lines:
        await message.answer(get_text(lang, "invalid_format"))
        return

    # Enforce max 4 features
    features = raw_lines[:MAX_FEATURES]
    features_json = json.dumps(features, ensure_ascii=False)

    data = await state.get_data()
    product_id = data.get("target_product_id")

    async with AsyncSessionLocal() as session:
        try:
            product = await session.get(Product, product_id)
            if not product:
                await message.answer(get_text(lang, "not_found"))
                return
            product.features = features_json
            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as exc:
            await session.rollback()
            logger.error("Features update error: %s", exc)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    preview = "\n".join(f"  ⭐ {f}" for f in features)
    await message.answer(f"{get_text(lang, 'features_updated')}\n\n{preview}")


# ── Edit price ────────────────────────────────────────────────────────────────

@products_router.callback_query(F.data == "action_edit_price")
async def prompt_new_price(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "enter_new_price"), reply_markup=_cancel_markup(lang))
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
        except Exception as exc:
            await session.rollback()
            logger.error("Price update error: %s", exc)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "price_updated").replace("{price}", _price_label(Decimal(new_price))))


# ── Add stock ─────────────────────────────────────────────────────────────────

@products_router.callback_query(F.data == "action_add_stock")
async def prompt_variant_selection(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    data = await state.get_data()
    product_id = data.get("target_product_id")

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Product).options(selectinload(Product.variants)).where(Product.id == product_id)
            )
            product = result.scalars().first()
            if not product:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            active_variants = [v for v in product.variants if v.is_active]
            if not active_variants:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            if len(active_variants) == 1:
                await state.update_data(target_variant_id=active_variants[0].id)
                await callback.message.answer(
                    get_text(lang, "enter_stock_lines") + "\n\n" + get_text(lang, "cancel_hint")
                )
                await state.set_state(ProductAdminStates.awaiting_stock_text)
                await callback.answer()
                return
        except Exception as exc:
            logger.error("DB error loading variants: %s", exc)
            await callback.answer(get_text(lang, "db_error"), show_alert=True)
            return

    keyboard = [
        [InlineKeyboardButton(text=f"{v.duration} — {v.price_label}", callback_data=f"pick_variant_{v.id}")]
        for v in active_variants
    ]
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")])

    await callback.message.edit_text(
        text=get_text(lang, "select_variant"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )
    await state.set_state(ProductAdminStates.selecting_variant_for_stock)
    await callback.answer()


@products_router.callback_query(F.data.startswith("pick_variant_"), ProductAdminStates.selecting_variant_for_stock)
async def variant_selected_for_stock(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    variant_id = callback.data.removeprefix("pick_variant_")
    await state.update_data(target_variant_id=variant_id)
    await callback.message.answer(get_text(lang, "enter_stock_lines") + "\n\n" + get_text(lang, "cancel_hint"))
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
    variant_id = data.get("target_variant_id")
    inserted = 0

    async with AsyncSessionLocal() as session:
        try:
            variant = await session.get(ProductVariant, variant_id)
            if not variant or variant.product_id != product_id:
                await message.answer(get_text(lang, "not_found"))
                return
            for credential in credentials:
                exists = await session.execute(
                    select(InventoryItem).where(
                        InventoryItem.product_id == product_id,
                        InventoryItem.variant_id == variant_id,
                        InventoryItem.credentials == credential,
                    ).with_for_update()
                )
                if exists.scalars().first():
                    continue
                session.add(InventoryItem(
                    product_id=product_id,
                    variant_id=variant_id,
                    credentials=credential,
                    status=ItemStatus.AVAILABLE,
                ))
                inserted += 1
            await session.commit()
            await redis_client.delete("cache:products:all")
        except Exception as exc:
            await session.rollback()
            logger.error("Stock insert error: %s", exc)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "stock_added").replace("{count}", str(inserted)))


# ── Upload logo ───────────────────────────────────────────────────────────────

@products_router.callback_query(F.data == "action_upload_logo")
async def prompt_logo_upload(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "send_logo") + "\n\n" + get_text(lang, "cancel_hint"))
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

    # Detect MIME by inspecting the first 16 bytes (magic bytes), no external library needed
    mime_type = "image/jpeg"
    sig = file_bytes[:16]
    if sig[:8] == b"\x89PNG\r\n\x1a\n":
        mime_type = "image/png"
    elif sig[:4] in (b"GIF8", b"GIF9"):
        mime_type = "image/gif"
    elif sig[:4] == b"RIFF" and sig[8:12] == b"WEBP":
        mime_type = "image/webp"
    elif sig[:2] not in (b"\xff\xd8",):
        # Not JPEG signature — reject
        await message.answer(get_text(lang, "image_required"))
        return

    extension = {
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/jpeg": ".jpg",
    }.get(mime_type, ".jpg")
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
        except Exception as exc:
            await session.rollback()
            logger.error("Logo upload DB error: %s", exc)
            await message.answer(get_text(lang, "db_error"))
            return

    await state.clear()
    await message.answer(get_text(lang, "logo_uploaded"))


# ── Bulk import ───────────────────────────────────────────────────────────────

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
            title = row[1].strip()
            brand = row[2].strip()
            if not title or not brand:
                raise ValueError("title and brand must not be empty.")
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
                "title": title,
                "brand": brand,
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


@products_router.callback_query(F.data == "bulk_import_products")
async def prompt_bulk_import(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "bulk_import_help") + "\n\n" + get_text(lang, "cancel_hint"))
    await state.set_state(ProductAdminStates.awaiting_bulk_import_file)
    await callback.answer()


@products_router.message(ProductAdminStates.awaiting_bulk_import_file, F.document)
async def process_bulk_import_file(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    document = message.document

    file_name = document.file_name.lower()
    if not file_name.endswith((".json", ".csv", ".txt")):
        await message.answer(get_text(lang, "txt_required"))
        return

    if document.file_size and document.file_size > 512_000:
        await message.answer(get_text(lang, "bulk_file_too_large"))
        return

    buffer = io.BytesIO()
    await message.bot.download(document, destination=buffer)
    content = buffer.getvalue().decode("utf-8-sig", errors="replace")

    if file_name.endswith(".json"):
        try:
            raw_payload = json.loads(content)
            raw_products = raw_payload.get("products") if isinstance(raw_payload, dict) else raw_payload
            if not isinstance(raw_products, list):
                raise ValueError("JSON root must be an array or an object with products array.")
            product_payloads = [_coerce_product_payload(item) for item in raw_products]
        except (json.JSONDecodeError, InvalidOperation, ValueError) as exc:
            await message.answer(get_text(lang, "bulk_import_errors") + f"\n{_h(exc)}", parse_mode="HTML")
            return

        inserted_credentials = 0
        try:
            async with AsyncSessionLocal() as session:
                for payload in product_payloads:
                    inserted_credentials += await _upsert_product_payload(session, payload)
                await session.commit()
        except Exception as exc:
            logger.error("JSON bulk import failed: %s", exc, exc_info=True)
            await message.answer(get_text(lang, "db_error"))
            return

        await redis_client.delete("cache:products:all")
        await state.clear()
        await message.answer(
            get_text(lang, "bulk_import_success")
            .replace("{products}", str(len(product_payloads)))
            .replace("{credentials}", str(inserted_credentials))
        )
        return

    rows, errors = parse_product_import(content)

    if errors:
        await message.answer(get_text(lang, "bulk_import_errors") + "\n" + "\n".join(errors[:10]))
        return

    inserted_credentials = 0
    chunk_size = 50
    chunk_errors = []

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        async with AsyncSessionLocal() as session:
            try:
                for row in chunk:
                    pid = row["product_id"]
                    vid = row["variant_id"]
                    product = await session.get(Product, pid)
                    if not product:
                        product = Product(
                            id=pid, title=row["title"], brand=row["brand"],
                            subtitle=row["subtitle"], category=row["category"], is_active=True,
                        )
                        session.add(product)
                    variant = await session.get(ProductVariant, vid)
                    if not variant:
                        variant = ProductVariant(
                            id=vid, product_id=pid, duration=row["duration"],
                            raw_price=row["raw_price"], price_label=f"{int(row['raw_price']):,}", is_active=True,
                        )
                        session.add(variant)
                    for cred in row["credentials"]:
                        exists = await session.execute(
                            select(InventoryItem).where(
                                InventoryItem.product_id == pid,
                                InventoryItem.variant_id == vid,
                                InventoryItem.credentials == cred,
                            )
                        )
                        if not exists.scalars().first():
                            session.add(InventoryItem(
                                product_id=pid, variant_id=vid,
                                credentials=cred, status=ItemStatus.AVAILABLE,
                            ))
                            inserted_credentials += 1
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.error("Chunk rollback at index %d: %s", i, exc)
                chunk_errors.append(f"Chunk {i // chunk_size + 1} failed: {exc}")

    await redis_client.delete("cache:products:all")
    await state.clear()

    if chunk_errors:
        await message.answer(get_text(lang, "bulk_import_errors") + "\n" + "\n".join(chunk_errors[:5]))
    else:
        await message.answer(
            get_text(lang, "bulk_import_success")
            .replace("{products}", str(len({row["product_id"] for row in rows})))
            .replace("{credentials}", str(inserted_credentials))
        )


@products_router.callback_query(F.data == "cancel_input")
async def inline_cancel(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.clear()
    try:
        await callback.message.edit_text(get_text(lang, "operation_cancelled"))
    except Exception:
        await callback.answer(get_text(lang, "operation_cancelled"))
    await callback.answer()


@products_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.clear()
    await message.answer(get_text(lang, "operation_cancelled"))
