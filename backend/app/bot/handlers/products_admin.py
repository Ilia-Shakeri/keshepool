import csv
import hashlib
import html
import io
import json
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Tuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from redis.exceptions import RedisError
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.bot.filters import IsAdminFilter
from app.core.redis import redis_client
from app.core.database import AsyncSessionLocal
from app.models import Product, InventoryItem, ItemStatus, utcnow
from app.bot.locales.translations import get_text
from app.bot.states import ProductAdminStates
from app.services.admin_audit_service import add_admin_audit
from app.services.cache_service import invalidate_catalog_cache, namespaced_key
from app.services.catalog_service import (
    CatalogMutationError,
    VariantOwnershipError,
    bulk_insert_stock,
    catalog_diagnostics,
    commit_catalog_change,
    patch_product_fields,
    set_active_variant_prices,
    set_product_active,
    upsert_product,
)

logger = logging.getLogger(__name__)

products_router = Router()
products_router.message.filter(IsAdminFilter())
products_router.callback_query.filter(IsAdminFilter())

ALLOWED_CATEGORIES = {"vpn", "music", "video", "ai", "social", "gaming", "tools", "edu", "finance"}
SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{2,120}$")
MAX_FEATURES = 4


async def _lang(user_id: int) -> str:
    try:
        lang = await redis_client.get(namespaced_key(f"admin-language:{user_id}"))
    except RedisError as exc:
        logger.warning("Admin language cache unavailable: %s", type(exc).__name__)
        return "fa"
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
    """Short deterministic token safe for Telegram callback data."""
    return _callback_token(brand)


def _callback_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _callback_value_map(values: list[str]) -> dict[str, str]:
    """Map short callback tokens to unchanged database identifiers."""
    mapping: dict[str, str] = {}
    for value in values:
        token = _callback_token(value)
        existing = mapping.get(token)
        if existing is not None and existing != value:
            raise ValueError("Callback token collision.")
        mapping[token] = value
    return mapping


def _button_label(value: object, max_chars: int = 60) -> str:
    """Keep dynamic inline-button labels within Telegram's text limit."""
    label = " ".join(str(value).split())
    if len(label) <= max_chars:
        return label
    return label[: max_chars - 1].rstrip() + "…"


def _cancel_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=get_text(lang, "broadcast_cancel_btn"),
                callback_data="cancel_input",
            )
        ]]
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

    brand_callback_map = _callback_value_map([brand for brand, _ in brands_data])
    for brand, cnt in brands_data:
        keyboard.append([
            InlineKeyboardButton(
                text=_button_label(f"📦 {brand} ({cnt})"),
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

    await state.update_data(brand_callback_map=brand_callback_map)
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
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "guided_add_product"), callback_data="guided_product_start")],
            [InlineKeyboardButton(text=get_text(lang, "advanced_product_json"), callback_data="advanced_product_json")],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")],
        ]
    )
    await callback.message.edit_text(
        get_text(lang, "product_add_method"),
        reply_markup=markup,
        parse_mode="HTML",
    )
    await callback.answer()


@products_router.callback_query(F.data == "advanced_product_json")
async def prompt_advanced_product_json(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "single_product_help"), reply_markup=_cancel_markup(lang), parse_mode="HTML")
    await state.set_state(ProductAdminStates.awaiting_single_product_json)
    await callback.answer()


def _guided_optional_markup(lang: str, skip_callback: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "skip_btn"), callback_data=skip_callback)],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="guided_edit_fields")],
            [InlineKeyboardButton(text=get_text(lang, "broadcast_cancel_btn"), callback_data="cancel_input")],
        ]
    )


def _guided_categories_markup(lang: str) -> InlineKeyboardMarkup:
    categories = sorted(ALLOWED_CATEGORIES)
    rows = [
        [
            InlineKeyboardButton(
                text=get_text(lang, f"category_{category}"),
                callback_data=f"guided_category_{category}",
            )
            for category in categories[index : index + 2]
        ]
        for index in range(0, len(categories), 2)
    ]
    rows.append([InlineKeyboardButton(text=get_text(lang, "broadcast_cancel_btn"), callback_data="cancel_input")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _guided_active_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=get_text(lang, "yes_active"), callback_data="guided_variant_active_yes"),
                InlineKeyboardButton(text=get_text(lang, "no_inactive"), callback_data="guided_variant_active_no"),
            ],
            [InlineKeyboardButton(text=get_text(lang, "broadcast_cancel_btn"), callback_data="cancel_input")],
        ]
    )


def _guided_after_variant_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "guided_add_variant"), callback_data="guided_add_variant")],
            [InlineKeyboardButton(text=get_text(lang, "guided_preview_btn"), callback_data="guided_show_preview")],
            [InlineKeyboardButton(text=get_text(lang, "guided_edit_fields"), callback_data="guided_edit_fields")],
            [InlineKeyboardButton(text=get_text(lang, "broadcast_cancel_btn"), callback_data="cancel_input")],
        ]
    )


async def _prompt_guided_title(target: Message, lang: str, state: FSMContext) -> None:
    await target.answer(get_text(lang, "guided_title_prompt"), reply_markup=_cancel_markup(lang))
    await state.set_state(ProductAdminStates.guided_title)


@products_router.callback_query(F.data == "guided_product_start")
async def start_guided_product(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.clear()
    await state.update_data(guided_variants=[])
    await _prompt_guided_title(callback.message, lang, state)
    await callback.answer()


@products_router.callback_query(F.data == "guided_edit_fields")
async def edit_guided_product_fields(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await _prompt_guided_title(callback.message, lang, state)
    await callback.answer()


@products_router.message(ProductAdminStates.guided_title)
async def process_guided_title(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    value = (message.text or "").strip()
    if not 2 <= len(value) <= 180:
        await message.answer(get_text(lang, "invalid_format"))
        return
    await state.update_data(guided_title=value)
    await message.answer(get_text(lang, "guided_brand_prompt"), reply_markup=_cancel_markup(lang))
    await state.set_state(ProductAdminStates.guided_brand)


@products_router.message(ProductAdminStates.guided_brand)
async def process_guided_brand(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    value = (message.text or "").strip()
    if not 2 <= len(value) <= 180:
        await message.answer(get_text(lang, "invalid_format"))
        return
    await state.update_data(guided_brand=value)
    await message.answer(
        get_text(lang, "guided_category_prompt"),
        reply_markup=_guided_categories_markup(lang),
    )
    await state.set_state(ProductAdminStates.guided_category)


@products_router.callback_query(F.data.startswith("guided_category_"), ProductAdminStates.guided_category)
async def process_guided_category(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    category = callback.data.removeprefix("guided_category_")
    if category not in ALLOWED_CATEGORIES:
        await callback.answer(get_text(lang, "invalid_format"), show_alert=True)
        return
    await state.update_data(guided_category=category)
    await callback.message.answer(
        get_text(lang, "guided_subtitle_prompt"),
        reply_markup=_guided_optional_markup(lang, "guided_skip_subtitle"),
    )
    await state.set_state(ProductAdminStates.guided_subtitle)
    await callback.answer()


async def _prompt_guided_features(target: Message, lang: str, state: FSMContext) -> None:
    await target.answer(
        get_text(lang, "guided_features_prompt"),
        reply_markup=_guided_optional_markup(lang, "guided_skip_features"),
    )
    await state.set_state(ProductAdminStates.guided_features)


@products_router.message(ProductAdminStates.guided_subtitle)
async def process_guided_subtitle(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    value = (message.text or "").strip()
    if not value or len(value) > 500:
        await message.answer(get_text(lang, "invalid_format"))
        return
    await state.update_data(guided_subtitle=value)
    await _prompt_guided_features(message, lang, state)


@products_router.callback_query(F.data == "guided_skip_subtitle", ProductAdminStates.guided_subtitle)
async def skip_guided_subtitle(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.update_data(guided_subtitle="")
    await _prompt_guided_features(callback.message, lang, state)
    await callback.answer()


async def _prompt_guided_logo(target: Message, lang: str, state: FSMContext) -> None:
    await target.answer(
        get_text(lang, "guided_logo_prompt"),
        reply_markup=_guided_optional_markup(lang, "guided_skip_logo"),
    )
    await state.set_state(ProductAdminStates.guided_logo)


@products_router.message(ProductAdminStates.guided_features)
async def process_guided_features(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    features = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
    if not features:
        await message.answer(get_text(lang, "invalid_format"))
        return
    await state.update_data(guided_features=features[:MAX_FEATURES])
    await _prompt_guided_logo(message, lang, state)


@products_router.callback_query(F.data == "guided_skip_features", ProductAdminStates.guided_features)
async def skip_guided_features(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.update_data(guided_features=[])
    await _prompt_guided_logo(callback.message, lang, state)
    await callback.answer()


async def _prompt_guided_variant_duration(target: Message, lang: str, state: FSMContext) -> None:
    await target.answer(get_text(lang, "guided_variant_duration_prompt"), reply_markup=_cancel_markup(lang))
    await state.set_state(ProductAdminStates.guided_variant_duration)


@products_router.message(ProductAdminStates.guided_logo)
async def process_guided_logo(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        if message.document.file_size and message.document.file_size > 2_000_000:
            await message.answer(get_text(lang, "logo_too_large"))
            return
        file_id = message.document.file_id
    if not file_id:
        await message.answer(get_text(lang, "image_required"))
        return
    await state.update_data(guided_logo_file_id=file_id)
    await _prompt_guided_variant_duration(message, lang, state)


@products_router.callback_query(F.data == "guided_skip_logo", ProductAdminStates.guided_logo)
async def skip_guided_logo(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.update_data(guided_logo_file_id=None)
    await _prompt_guided_variant_duration(callback.message, lang, state)
    await callback.answer()


@products_router.message(ProductAdminStates.guided_variant_duration)
async def process_guided_variant_duration(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    duration = (message.text or "").strip()
    if not 1 <= len(duration) <= 120:
        await message.answer(get_text(lang, "invalid_format"))
        return
    await state.update_data(guided_variant_duration=duration)
    await message.answer(get_text(lang, "guided_variant_price_prompt"), reply_markup=_cancel_markup(lang))
    await state.set_state(ProductAdminStates.guided_variant_price)


_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _positive_whole_number(raw: str) -> int | None:
    cleaned = raw.translate(_DIGIT_TRANSLATION).replace(",", "").replace("٬", "").strip()
    if not cleaned.isdigit():
        return None
    value = int(cleaned)
    return value if value > 0 else None


@products_router.message(ProductAdminStates.guided_variant_price)
async def process_guided_variant_price(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    price = _positive_whole_number(message.text or "")
    if price is None:
        await message.answer(get_text(lang, "invalid_format"))
        return
    await state.update_data(guided_variant_price=price)
    await message.answer(
        get_text(lang, "guided_variant_active_prompt"),
        reply_markup=_guided_active_markup(lang),
    )
    await state.set_state(ProductAdminStates.guided_variant_active)


@products_router.callback_query(F.data.startswith("guided_variant_active_"), ProductAdminStates.guided_variant_active)
async def process_guided_variant_active(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    active = callback.data.endswith("_yes")
    await state.update_data(guided_variant_active=active)
    await callback.message.answer(
        get_text(lang, "guided_variant_stock_prompt"),
        reply_markup=_guided_optional_markup(lang, "guided_skip_stock"),
    )
    await state.set_state(ProductAdminStates.guided_variant_stock)
    await callback.answer()


async def _finish_guided_variant(target: Message, lang: str, state: FSMContext, credentials: list[str]) -> None:
    data = await state.get_data()
    variants = list(data.get("guided_variants") or [])
    variants.append(
        {
            "duration": data.get("guided_variant_duration"),
            "rawPrice": data.get("guided_variant_price"),
            "isActive": bool(data.get("guided_variant_active")),
            "credentials": credentials,
        }
    )
    await state.update_data(guided_variants=variants)
    await target.answer(get_text(lang, "guided_preview_btn"), reply_markup=_guided_after_variant_markup(lang))
    await state.set_state(ProductAdminStates.guided_preview)


@products_router.message(ProductAdminStates.guided_variant_stock)
async def process_guided_variant_stock(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    credentials = [line.strip() for line in (message.text or "").splitlines() if line.strip()]
    if not credentials:
        await message.answer(get_text(lang, "invalid_format"))
        return
    await _finish_guided_variant(message, lang, state, credentials)


@products_router.callback_query(F.data == "guided_skip_stock", ProductAdminStates.guided_variant_stock)
async def skip_guided_variant_stock(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await _finish_guided_variant(callback.message, lang, state, [])
    await callback.answer()


@products_router.callback_query(F.data == "guided_add_variant")
async def add_another_guided_variant(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await _prompt_guided_variant_duration(callback.message, lang, state)
    await callback.answer()


def _guided_product_id(title: str, brand: str) -> str:
    digest = hashlib.sha256(f"{brand.strip().lower()}|{title.strip().lower()}".encode("utf-8")).hexdigest()[:20]
    return f"guided_{digest}"


def _guided_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    product_id = _guided_product_id(str(data["guided_title"]), str(data["guided_brand"]))
    variants = []
    for index, item in enumerate(data.get("guided_variants") or [], start=1):
        variant_digest = hashlib.sha256(
            f"{product_id}|{index}|{item['duration']}".encode("utf-8")
        ).hexdigest()[:12]
        variants.append(
            {
                "id": f"{product_id}_v_{variant_digest}",
                "duration": item["duration"],
                "rawPrice": item["rawPrice"],
                "priceLabel": _price_label(Decimal(str(item["rawPrice"]))),
                "isActive": item["isActive"],
                "credentials": item["credentials"],
            }
        )
    return {
        "id": product_id,
        "title": data["guided_title"],
        "brand": data["guided_brand"],
        "subtitle": data.get("guided_subtitle") or "",
        "category": data["guided_category"],
        "features": data.get("guided_features") or None,
        "icon": "Box",
        "gradient": "from-gray-700 to-black",
        "variants": variants,
    }


def _guided_preview_text(lang: str, data: Dict[str, Any]) -> str:
    variants = data.get("guided_variants") or []
    variant_lines = []
    for index, item in enumerate(variants, start=1):
        active = get_text(lang, "yes_active") if item.get("isActive") else get_text(lang, "no_inactive")
        variant_lines.append(
            f"{index}. {_h(item.get('duration'))} — {_price_label(Decimal(str(item.get('rawPrice'))))} — {_h(active)} — {len(item.get('credentials') or [])}"
        )
    features = " | ".join(_h(value) for value in (data.get("guided_features") or []))
    return get_text(lang, "guided_preview").format(
        title=_h(data.get("guided_title")),
        brand=_h(data.get("guided_brand")),
        category=_h(get_text(lang, f"category_{data.get('guided_category')}")),
        subtitle=_h(data.get("guided_subtitle") or get_text(lang, "subtitle_none")),
        features=features or _h(get_text(lang, "features_none")),
        logo=_h(get_text(lang, "logo_attached") if data.get("guided_logo_file_id") else get_text(lang, "logo_none")),
        variants="\n".join(variant_lines),
    )


@products_router.callback_query(F.data == "guided_show_preview")
async def show_guided_preview(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    data = await state.get_data()
    if not data.get("guided_variants"):
        await callback.answer(get_text(lang, "guided_need_variant"), show_alert=True)
        return
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "guided_confirm"), callback_data="guided_confirm_save")],
            [InlineKeyboardButton(text=get_text(lang, "guided_edit_fields"), callback_data="guided_edit_fields")],
            [InlineKeyboardButton(text=get_text(lang, "guided_add_variant"), callback_data="guided_add_variant")],
            [InlineKeyboardButton(text=get_text(lang, "broadcast_cancel_btn"), callback_data="cancel_input")],
        ]
    )
    await callback.message.edit_text(
        _guided_preview_text(lang, data),
        reply_markup=markup,
        parse_mode="HTML",
    )
    await state.set_state(ProductAdminStates.guided_preview)
    await callback.answer()


async def _store_guided_logo(bot, file_id: str, product_id: str) -> str:
    buffer = io.BytesIO()
    await bot.download(file_id, destination=buffer)
    file_bytes = buffer.getvalue()
    if len(file_bytes) > 2_000_000:
        raise ValueError("logo_too_large")
    sig = file_bytes[:16]
    if sig[:8] == b"\x89PNG\r\n\x1a\n":
        extension = ".png"
    elif sig[:4] == b"RIFF" and sig[8:12] == b"WEBP":
        extension = ".webp"
    elif sig[:2] == b"\xff\xd8":
        extension = ".jpg"
    else:
        raise ValueError("image_required")
    asset_dir = Path(settings.ASSET_ROOT) / "product-assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    target_path = asset_dir / f"{product_id}{extension}"
    target_path.write_bytes(file_bytes)
    return f"{settings.PUBLIC_ASSET_BASE_URL.rstrip('/')}/product-assets/{target_path.name}"


@products_router.callback_query(F.data == "guided_confirm_save", ProductAdminStates.guided_preview)
async def confirm_guided_product(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    data = await state.get_data()
    if not data.get("guided_variants"):
        await callback.answer(get_text(lang, "guided_need_variant"), show_alert=True)
        return
    payload = _guided_payload(data)
    logo_file_id = data.get("guided_logo_file_id")
    if logo_file_id:
        try:
            payload["assetUrl"] = await _store_guided_logo(callback.bot, logo_file_id, payload["id"])
            payload["icon"] = "Image"
        except ValueError as exc:
            await callback.answer(get_text(lang, str(exc)), show_alert=True)
            return
    try:
        async with AsyncSessionLocal() as session:
            result = await upsert_product(session, payload, replace_variants=True, commit=False)
            await add_admin_audit(
                session,
                actor_telegram_id=callback.from_user.id,
                action="product.guided_upsert",
                target_type="product",
                target_id=payload["id"],
                details={
                    "variant_count": len(payload["variants"]),
                    "submitted_stock_count": sum(len(item["credentials"]) for item in payload["variants"]),
                    "inserted_stock_count": result.inserted_stock_count,
                    "duplicate_stock_count": result.duplicate_stock_count,
                },
            )
            await commit_catalog_change(session)
    except (CatalogMutationError, VariantOwnershipError) as exc:
        logger.warning("Guided product rejected: %s", exc)
        await callback.answer(get_text(lang, "single_product_invalid"), show_alert=True)
        return
    except Exception as exc:
        logger.error("Guided product save failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        get_text(lang, "guided_saved")
        .replace("{inserted}", str(result.inserted_stock_count))
        .replace("{duplicates}", str(result.duplicate_stock_count))
    )
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


async def _upsert_product_payload(session, payload: Dict[str, Any]):
    """Apply a full admin payload through the shared catalog mutation service."""
    return await upsert_product(
        session,
        payload,
        replace_variants=True,
        commit=False,
    )


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
            result = await _upsert_product_payload(session, payload)
            await add_admin_audit(
                session,
                actor_telegram_id=message.from_user.id,
                action="product.json_upsert",
                target_type="product",
                target_id=payload["id"],
                details={
                    "variant_count": len(payload["variants"]),
                    "inserted_stock_count": result.inserted_stock_count,
                    "duplicate_stock_count": result.duplicate_stock_count,
                },
            )
            await commit_catalog_change(session)
    except (CatalogMutationError, VariantOwnershipError) as exc:
        logger.warning("Single product payload conflicts with catalog data: %s", exc)
        await message.answer(get_text(lang, "single_product_invalid"))
        return
    except Exception as exc:
        logger.error("Single product upsert failed: %s", exc, exc_info=True)
        await message.answer(get_text(lang, "db_error"))
        return

    await state.clear()
    await message.answer(get_text(lang, "single_product_success"))


@products_router.callback_query(F.data.startswith("sel_brand_"))
async def handle_brand_selection(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    brand_hash_val = callback.data.removeprefix("sel_brand_")

    state_data = await state.get_data()
    target_brand = (state_data.get("brand_callback_map") or {}).get(brand_hash_val)

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

    # Old messages did not carry a state map. Keep their short brand tokens valid.
    if target_brand is None:
        target_brand = next(
            (product.brand for product in all_products if _brand_hash(product.brand) == brand_hash_val),
            None,
        )

    if not target_brand:
        await callback.answer(get_text(lang, "brand_not_found"), show_alert=True)
        return

    brand_products = [p for p in all_products if p.brand == target_brand]
    keyboard: list[list[InlineKeyboardButton]] = []

    product_callback_map = _callback_value_map([product.id for product in brand_products])
    for product in brand_products:
        icon = "✅" if product.is_active else "⛔"
        token = _callback_token(product.id)
        keyboard.append([
            InlineKeyboardButton(
                text=_button_label(f"{icon} {product.title} [{product.id}]"),
                callback_data=f"edit_prod_{token}",
            )
        ])

    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")])

    await state.update_data(
        current_brand=target_brand,
        product_callback_map=product_callback_map,
    )
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
    callback_token = callback.data.removeprefix("edit_prod_")
    data = await state.get_data()
    product_id = (data.get("product_callback_map") or {}).get(callback_token)
    if product_id is None and SAFE_ID_RE.fullmatch(callback_token):
        # Backward compatibility for buttons created before callback token maps.
        product_id = callback_token
    if product_id is None:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return
    await state.update_data(target_product_id=product_id)

    try:
        async with AsyncSessionLocal() as session:
            product_result = await session.execute(
                select(Product).options(selectinload(Product.variants)).where(Product.id == product_id)
            )
            product = product_result.scalars().first()
            if not product:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            now = utcnow()
            sellable_time = or_(InventoryItem.expires_at.is_(None), InventoryItem.expires_at > now)
            stock_result = await session.execute(
                select(
                    InventoryItem.variant_id,
                    func.count(case((and_(InventoryItem.status == ItemStatus.AVAILABLE, sellable_time), 1))).label("available"),
                    func.count(case((and_(InventoryItem.status == ItemStatus.RESERVED, sellable_time), 1))).label("reserved"),
                    func.count(case((and_(InventoryItem.status == ItemStatus.ASSIGNED, sellable_time), 1))).label("assigned"),
                    func.count(
                        case(
                            (
                                or_(
                                    InventoryItem.status == ItemStatus.EXPIRED,
                                    InventoryItem.expires_at <= now,
                                ),
                                1,
                            )
                        )
                    ).label("expired"),
                )
                .where(InventoryItem.product_id == product.id)
                .group_by(InventoryItem.variant_id)
            )
            stock_by_variant = {
                row.variant_id: {
                    "available": int(row.available),
                    "reserved": int(row.reserved),
                    "assigned": int(row.assigned),
                    "expired": int(row.expired),
                }
                for row in stock_result
            }
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
                InlineKeyboardButton(text=get_text(lang, "variant_price_btn"), callback_data="action_edit_price"),
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
                InlineKeyboardButton(text=get_text(lang, "variant_toggle_btn"), callback_data="action_manage_variants"),
            ],
            [
                InlineKeyboardButton(
                    text=get_text(lang, "catalog_diagnostics"),
                    callback_data="action_catalog_diagnostics",
                ),
                InlineKeyboardButton(
                    text=get_text(lang, "refresh_catalog_cache"),
                    callback_data="action_refresh_catalog_cache",
                ),
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
        except (TypeError, json.JSONDecodeError) as exc:
            logger.warning("Invalid stored feature data for product %s: %s", product_id, exc)

    variant_stock_lines = []
    for variant in product.variants:
        counts = stock_by_variant.get(
            variant.id,
            {"available": 0, "reserved": 0, "assigned": 0, "expired": 0},
        )
        state_icon = "✅" if variant.is_active else "⛔"
        variant_stock_lines.append(
            f"{state_icon} <b>{_h(variant.duration)}</b> — "
            + get_text(lang, "stock_breakdown").format(**counts)
        )
    stock_count = sum(item["available"] for item in stock_by_variant.values())
    text = (
        f"{get_text(lang, 'config_product')} <code>[{_h(product_id)}]</code>\n"
        f"📦 {get_text(lang, 'available_stock')}: <b>{stock_count}</b>"
        f"{_h(features_preview)}\n\n"
        + "\n".join(variant_stock_lines)
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
            new_state = not product.is_active
            await set_product_active(session, product_id, new_state)
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


@products_router.callback_query(F.data == "action_catalog_diagnostics")
async def show_catalog_diagnostics(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    product_id = (await state.get_data()).get("target_product_id")
    try:
        async with AsyncSessionLocal() as session:
            diagnostics = await catalog_diagnostics(session, product_id)
    except Exception as exc:
        logger.error("Catalog diagnostics failed: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    visibility = get_text(
        lang,
        f"catalog_reason_{diagnostics.get('visibility_reason', 'not_found')}",
    )
    cache_status = get_text(
        lang,
        f"catalog_cache_{diagnostics.get('cache_status', 'unknown')}",
    )
    report = get_text(lang, "catalog_diagnostics_report").format(
        visibility=_h(visibility),
        variants=int(diagnostics.get("active_variant_count", 0)),
        stock=int(diagnostics.get("available_stock_count", 0)),
        cache=_h(cache_status),
    )
    await callback.message.answer(report, parse_mode="HTML")
    await callback.answer()


@products_router.callback_query(F.data == "action_refresh_catalog_cache")
async def refresh_catalog_cache(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    cache_invalidated = await invalidate_catalog_cache()
    message_key = "catalog_cache_refreshed" if cache_invalidated else "catalog_cache_unavailable"
    await callback.answer(get_text(lang, message_key), show_alert=True)


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
            await set_product_active(
                session,
                product_id,
                False,
                deactivate_variants=True,
            )
    except CatalogMutationError:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return
    except Exception as exc:
        logger.error("Product delete failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

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
            await patch_product_fields(session, product_id, {"title": new_name})
        except CatalogMutationError:
            await message.answer(get_text(lang, "not_found"))
            return
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
            await patch_product_fields(session, product_id, {"subtitle": new_subtitle})
        except CatalogMutationError:
            await message.answer(get_text(lang, "not_found"))
            return
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
                current_label = get_text(lang, "current_label")
                current_preview = f"\n\n{current_label}:\n" + "\n".join(f"  • {f}" for f in fl)
    except Exception as exc:
        logger.warning("Could not load feature preview for product %s: %s", product_id, exc)

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
            await patch_product_fields(session, product_id, {"features": features_json})
        except CatalogMutationError:
            await message.answer(get_text(lang, "not_found"))
            return
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
    new_price = _positive_whole_number(message.text or "")
    if new_price is None:
        await message.answer(get_text(lang, "invalid_format"))
        return

    data = await state.get_data()
    product_id = data.get("target_product_id")

    async with AsyncSessionLocal() as session:
        try:
            await set_active_variant_prices(session, product_id, Decimal(str(new_price)))
        except CatalogMutationError:
            await message.answer(get_text(lang, "invalid_format"))
            return
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

    variant_callback_map = _callback_value_map([variant.id for variant in active_variants])
    keyboard = []
    for variant in active_variants:
        token = _callback_token(variant.id)
        keyboard.append([
            InlineKeyboardButton(
                text=_button_label(f"{variant.duration} — {variant.price_label}"),
                callback_data=f"pick_variant_{token}",
            )
        ])
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_inventory")])

    await state.update_data(variant_callback_map=variant_callback_map)

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
    callback_token = callback.data.removeprefix("pick_variant_")
    data = await state.get_data()
    variant_id = (data.get("variant_callback_map") or {}).get(callback_token)
    if variant_id is None and SAFE_ID_RE.fullmatch(callback_token):
        variant_id = callback_token
    if variant_id is None:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return
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
    async with AsyncSessionLocal() as session:
        try:
            result = await bulk_insert_stock(
                session,
                product_id=product_id,
                variant_id=variant_id,
                credentials=credentials,
            )
            inserted = result.inserted_stock_count
        except CatalogMutationError:
            await message.answer(get_text(lang, "not_found"))
            return
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
            await patch_product_fields(
                session,
                product_id,
                {"asset_url": asset_url, "icon": "Image"},
            )
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


def _group_product_import_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group flat file rows so each product is mutated once per import."""
    grouped: dict[str, Dict[str, Any]] = {}
    variant_owners: dict[str, str] = {}
    for row in rows:
        product_id = row["product_id"]
        variant_id = row["variant_id"]
        known_owner = variant_owners.setdefault(variant_id, product_id)
        if known_owner != product_id:
            raise ValueError(
                f"Variant {variant_id} is assigned to both {known_owner} and {product_id}."
            )

        product_payload = grouped.setdefault(
            product_id,
            {
                "id": product_id,
                "title": row["title"],
                "brand": row["brand"],
                "subtitle": row["subtitle"],
                "category": row["category"],
                "icon": "Box",
                "asset_url": None,
                "gradient": "from-gray-700 to-black",
                "features": None,
                "variants": {},
            },
        )
        variant_payload = product_payload["variants"].setdefault(
            variant_id,
            {
                "id": variant_id,
                "duration": row["duration"],
                "raw_price": row["raw_price"],
                "price_label": f"{int(row['raw_price']):,}",
                "credentials": [],
            },
        )
        if (
            variant_payload["duration"] != row["duration"]
            or Decimal(str(variant_payload["raw_price"])) != Decimal(str(row["raw_price"]))
        ):
            raise ValueError(f"Variant {variant_id} has conflicting duration or price rows.")
        variant_payload["credentials"].extend(row["credentials"])

    payloads = []
    for product_payload in grouped.values():
        product_payload["variants"] = list(product_payload["variants"].values())
        payloads.append(product_payload)
    return payloads


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
                    result = await _upsert_product_payload(session, payload)
                    inserted_credentials += result.inserted_stock_count
                await commit_catalog_change(session)
        except (CatalogMutationError, VariantOwnershipError) as exc:
            logger.warning("JSON bulk import conflicts with catalog data: %s", exc)
            await message.answer(
                get_text(lang, "bulk_import_errors") + f"\n{_h(exc)}",
                parse_mode="HTML",
            )
            return
        except Exception as exc:
            logger.error("JSON bulk import failed: %s", exc, exc_info=True)
            await message.answer(get_text(lang, "db_error"))
            return

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

    try:
        product_payloads = _group_product_import_rows(rows)
        inserted_credentials = 0
        async with AsyncSessionLocal() as session:
            for payload in product_payloads:
                result = await upsert_product(
                    session,
                    payload,
                    replace_variants=False,
                    commit=False,
                )
                inserted_credentials += result.inserted_stock_count
            await commit_catalog_change(session)
    except (CatalogMutationError, VariantOwnershipError, ValueError) as exc:
        logger.warning("Flat catalog import rejected: %s", exc)
        await message.answer(get_text(lang, "bulk_import_errors") + f"\n{_h(exc)}")
        return
    except Exception as exc:
        logger.error("Flat catalog import failed: %s", exc, exc_info=True)
        await message.answer(get_text(lang, "db_error"))
        return

    await state.clear()
    await message.answer(
        get_text(lang, "bulk_import_success")
        .replace("{products}", str(len(product_payloads)))
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
