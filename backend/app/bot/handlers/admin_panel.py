import html
import logging
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.bot.filters import IsAdminFilter
from app.bot.states import AdminPanelStates
from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.services.rate_service import get_usdt_rate, set_usdt_rate
from app.models import (
    CashoutRequest,
    CashoutRequestStatus,
    Notification,
    Order,
    OrderStatus,
    Transaction,
    TransactionStatus,
    User,
    utcnow,
)
from app.bot.locales.translations import get_text

logger = logging.getLogger(__name__)

admin_router = Router()
admin_router.message.filter(IsAdminFilter())
admin_router.callback_query.filter(IsAdminFilter())

PAGE_SIZE = 8


async def get_admin_lang(user_id: int) -> str:
    lang = await redis_client.get(f"admin_lang:{user_id}")
    return lang or "fa"


def _h(text: object) -> str:
    """Escape arbitrary values for Telegram HTML parse mode."""
    return html.escape(str(text) if text is not None else "")


def get_persistent_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🏠 " + get_text(lang, "home_btn")),
                KeyboardButton(text="📦 " + get_text(lang, "inventory_title")),
            ],
            [
                KeyboardButton(text="👥 " + get_text(lang, "users_title")),
                KeyboardButton(text="📊 " + get_text(lang, "report_btn")),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_main_menu_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 " + get_text(lang, "users_title"), callback_data="manage_users_0"),
                InlineKeyboardButton(text="📦 " + get_text(lang, "inventory_title"), callback_data="manage_inventory"),
            ],
            [
                InlineKeyboardButton(text="💱 " + get_text(lang, "cashouts_title"), callback_data="manage_cashouts_0"),
                InlineKeyboardButton(text="📊 " + get_text(lang, "stats_title"), callback_data="manage_stats"),
            ],
            [
                InlineKeyboardButton(text="📢 " + get_text(lang, "broadcast_title"), callback_data="broadcast_msg"),
                InlineKeyboardButton(text="🔍 " + get_text(lang, "search_user_title"), callback_data="search_user"),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "rates_btn"), callback_data="manage_rates"),
                InlineKeyboardButton(text=get_text(lang, "report_btn"), callback_data="force_report"),
            ],
            [
                InlineKeyboardButton(text=get_text(lang, "toggle_lang"), callback_data="toggle_language"),
            ],
        ]
    )


async def build_report_text() -> str:
    """Build a comprehensive system statistics report."""
    async with AsyncSessionLocal() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        new_today = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= today_start)
        ) or 0
        total_orders = await session.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.ACTIVE)
        ) or 0
        total_revenue = await session.scalar(
            select(func.sum(Order.total_amount)).where(Order.status == OrderStatus.ACTIVE)
        ) or 0
        pending_tx = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.PENDING)
        ) or 0
        pending_cashouts = await session.scalar(
            select(func.count(CashoutRequest.id)).where(CashoutRequest.status == CashoutRequestStatus.PENDING)
        ) or 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"📊 <b>گزارش سیستم کش‌پول</b>\n"
        f"🕐 {_h(now)}\n\n"
        f"👥 کل کاربران: <b>{total_users:,}</b>\n"
        f"🆕 ثبت‌نام امروز: <b>{new_today:,}</b>\n"
        f"📦 سفارشات فعال: <b>{total_orders:,}</b>\n"
        f"💰 کل درآمد: <b>{float(total_revenue):,.0f}</b> تومان\n"
        f"⏳ تراکنش‌های معلق: <b>{pending_tx}</b>\n"
        f"💱 درخواست نقد معلق: <b>{pending_cashouts}</b>"
    )


# ── Entry points ──────────────────────────────────────────────────────────────

@admin_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_admin_lang(message.from_user.id)
    await message.answer(
        text=get_text(lang, "main_menu"),
        reply_markup=get_main_menu_markup(lang),
        parse_mode="HTML",
    )
    await message.answer(
        text=get_text(lang, "persistent_hint"),
        reply_markup=get_persistent_menu(lang),
    )


@admin_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await message.answer(get_text(lang, "operation_cancelled"))


# ── Persistent-menu shortcuts ─────────────────────────────────────────────────

@admin_router.message(F.text.func(lambda t: t and t.startswith("🏠")))
async def shortcut_home(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await message.answer(
        text=get_text(lang, "main_menu"),
        reply_markup=get_main_menu_markup(lang),
        parse_mode="HTML",
    )


@admin_router.message(F.text.func(lambda t: t and t.startswith("📦")))
async def shortcut_inventory(message: Message, state: FSMContext):
    from app.bot.handlers.products_admin import show_brands
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await show_brands(message, lang, state, send_new=True)


@admin_router.message(F.text.func(lambda t: t and t.startswith("👥")))
async def shortcut_users(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await _send_users_page(message, lang, page=0, send_new=True)


@admin_router.message(F.text.func(lambda t: t and t.startswith("📊")))
async def shortcut_report(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    try:
        text = await build_report_text()
        await message.answer(text=text, parse_mode="HTML")
    except Exception as exc:
        logger.error("Report shortcut failed: %s", exc)
        await message.answer(get_text(lang, "db_error"))


# ── Language toggle ───────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "toggle_language")
async def process_toggle_language(callback: CallbackQuery):
    current = await get_admin_lang(callback.from_user.id)
    new_lang = "en" if current == "fa" else "fa"
    await redis_client.set(f"admin_lang:{callback.from_user.id}", new_lang)
    await callback.message.edit_text(
        text=get_text(new_lang, "main_menu"),
        reply_markup=get_main_menu_markup(new_lang),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(
        text=get_text(lang, "main_menu"),
        reply_markup=get_main_menu_markup(lang),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Statistics ────────────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "manage_stats")
async def show_stats(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        text = await build_report_text()
    except Exception as exc:
        logger.error("Stats error: %s", exc)
        text = get_text(lang, "db_error")
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")]]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "force_report")
async def process_force_report(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        text = await build_report_text()
        # Send full report directly to the admin who triggered it
        await callback.message.answer(text=text, parse_mode="HTML")
        # Also relay to group chat if configured and different chat
        from app.core.config import settings
        if settings.ADMIN_GROUP_CHAT_ID and str(callback.message.chat.id) != str(settings.ADMIN_GROUP_CHAT_ID):
            try:
                await callback.bot.send_message(
                    chat_id=settings.ADMIN_GROUP_CHAT_ID,
                    text=text,
                    parse_mode="HTML",
                )
            except Exception:
                pass
    except Exception as exc:
        logger.error("Force report failed: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    await callback.answer()


# ── User management ───────────────────────────────────────────────────────────

async def _send_users_page(target, lang: str, page: int, send_new: bool = False) -> None:
    try:
        async with AsyncSessionLocal() as session:
            total_users = await session.scalar(select(func.count(User.id))) or 0
            result = await session.execute(
                select(User)
                .options(selectinload(User.wallet))
                .order_by(User.id.desc())
                .limit(PAGE_SIZE)
                .offset(page * PAGE_SIZE)
            )
            users = result.scalars().all()
    except Exception as exc:
        logger.error("DB error in _send_users_page: %s", exc)
        err = get_text(lang, "db_error")
        if send_new:
            await target.answer(err)
        else:
            await target.message.answer(err)
        return

    lines = [f"<b>{get_text(lang, 'users_title')}</b>\nTotal: {total_users:,}\n"]
    user_buttons: list[InlineKeyboardButton] = []

    for u in users:
        balance = float(u.wallet.balance) if u.wallet else 0.0
        uname = _h(u.username or "—")
        fname = _h(u.first_name or "")
        lines.append(f"• <code>{u.id}</code> @{uname} {fname} | <b>{balance:,.0f}</b>")
        label = (u.first_name or u.username or str(u.telegram_id))[:20]
        user_buttons.append(
            InlineKeyboardButton(text=f"👤 {label}", callback_data=f"user_detail_{u.id}")
        )

    text = "\n".join(lines)

    # Pair user buttons into rows of 2
    keyboard: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(user_buttons), 2):
        keyboard.append(user_buttons[i : i + 2])

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"manage_users_{page - 1}"))
    if (page + 1) * PAGE_SIZE < total_users:
        nav.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"manage_users_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if send_new:
        await target.answer(text=text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("manage_users_"))
async def process_manage_users(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    parts = callback.data.split("_")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _send_users_page(callback, lang, page)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("user_detail_"))
async def view_user_detail(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    user_id = int(callback.data.removeprefix("user_detail_"))

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).options(selectinload(User.wallet)).where(User.id == user_id)
            )
            user = result.scalars().first()
            if not user:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            order_count = await session.scalar(
                select(func.count(Order.id)).where(Order.user_id == user.id)
            ) or 0
    except Exception as exc:
        logger.error("DB error in user_detail: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    balance = float(user.wallet.balance) if user.wallet else 0.0
    created = user.created_at.strftime("%Y-%m-%d") if user.created_at else "?"
    last_seen = user.last_seen_at.strftime("%Y-%m-%d %H:%M") if user.last_seen_at else "?"

    text = (
        f"👤 <b>{_h(user.first_name)} {_h(user.last_name or '')}</b>\n"
        f"🆔 Telegram ID: <code>{_h(user.telegram_id)}</code>\n"
        f"📛 Username: @{_h(user.username or 'N/A')}\n"
        f"💰 Balance: <b>{balance:,.0f}</b> Toman\n"
        f"📦 Orders: <b>{order_count}</b>\n"
        f"⭐ Premium: {'✅' if user.is_premium else '—'}\n"
        f"🔑 Role: <code>{_h(user.role)}</code>\n"
        f"📅 Registered: {created}\n"
        f"🕐 Last Seen: {last_seen}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔔 Send Notification", callback_data=f"notify_user_{user.id}"),
                InlineKeyboardButton(text="📦 Orders", callback_data=f"user_orders_{user.id}"),
            ],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_users_0")],
        ]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("user_orders_"))
async def view_user_orders(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    user_id = int(callback.data.removeprefix("user_orders_"))

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Order)
                .options(selectinload(Order.product), selectinload(Order.variant))
                .where(Order.user_id == user_id)
                .order_by(Order.created_at.desc())
                .limit(10)
            )
            orders = result.scalars().all()
    except Exception as exc:
        logger.error("DB error in user_orders: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    if not orders:
        text = "📦 No orders found for this user."
    else:
        lines = [f"📦 <b>Last {len(orders)} orders:</b>\n"]
        for o in orders:
            product_name = _h(o.product.brand if o.product else "?")
            duration = _h(o.variant.duration if o.variant else "?")
            amount = float(o.total_amount)
            date = o.created_at.strftime("%m/%d") if o.created_at else "?"
            icon = "✅" if o.status.value == "active" else "⛔"
            lines.append(f"{icon} {product_name} {duration} — {amount:,.0f}T — {date}")
        text = "\n".join(lines)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data=f"user_detail_{user_id}")]]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("notify_user_"))
async def prompt_user_notification(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.removeprefix("notify_user_"))
    await state.update_data(notify_target_user_id=user_id)
    await callback.message.answer(
        "✏️ Send the notification.\n<b>Line 1</b> = Title\n<b>Rest</b> = Body\n\n/cancel to abort.",
        parse_mode="HTML",
    )
    await state.set_state(AdminPanelStates.awaiting_notification_text)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_notification_text)
async def process_user_notification(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    lines = message.text.strip().splitlines()
    title = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else title

    if not title:
        await message.answer("❌ Empty message.")
        return

    data = await state.get_data()
    target_id = data.get("notify_target_user_id")
    if not target_id:
        await message.answer("❌ Target user lost. Start over.")
        await state.clear()
        return

    try:
        async with AsyncSessionLocal() as session:
            session.add(Notification(user_id=target_id, title=title, description=body or title))
            await session.commit()
    except Exception as exc:
        logger.error("Notification insert failed: %s", exc)
        await message.answer(get_text(lang, "db_error"))
        await state.clear()
        return

    await state.clear()
    await message.answer("✅ Notification sent to user's in-app inbox.")


# ── Search user ───────────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "search_user")
async def prompt_search(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "search_prompt") + "\n\n/cancel to abort.")
    await state.set_state(AdminPanelStates.awaiting_search_query)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_search_query)
async def process_search(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    query = message.text.strip().lstrip("@")
    await state.clear()

    try:
        async with AsyncSessionLocal() as session:
            if query.isdigit():
                result = await session.execute(
                    select(User).options(selectinload(User.wallet))
                    .where(User.telegram_id == query)
                )
            else:
                result = await session.execute(
                    select(User).options(selectinload(User.wallet))
                    .where(User.username.ilike(f"%{query}%"))
                    .limit(5)
                )
            users = result.scalars().all()
    except Exception as exc:
        logger.error("Search error: %s", exc)
        await message.answer(get_text(lang, "db_error"))
        return

    if not users:
        await message.answer(get_text(lang, "user_not_found"))
        return

    for user in users:
        balance = float(user.wallet.balance) if user.wallet else 0.0
        text = (
            f"👤 <b>{_h(user.first_name)} {_h(user.last_name or '')}</b>\n"
            f"🆔 <code>{_h(user.telegram_id)}</code> | @{_h(user.username or 'N/A')}\n"
            f"💰 Balance: <b>{balance:,.0f}</b> Toman | Role: <code>{_h(user.role)}</code>"
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="👁 View Detail", callback_data=f"user_detail_{user.id}")
            ]]
        )
        await message.answer(text=text, reply_markup=markup, parse_mode="HTML")


# ── Broadcast ─────────────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "broadcast_msg")
async def prompt_broadcast(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "broadcast_prompt"))
    await state.set_state(AdminPanelStates.awaiting_broadcast_message)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_broadcast_message)
async def process_broadcast(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    lines = message.text.strip().splitlines()
    title = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else title

    if not title:
        await message.answer("❌ Empty message.")
        return

    await state.clear()
    count = 0
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User.id))
            user_ids = [row[0] for row in result.all()]
            for uid in user_ids:
                session.add(Notification(user_id=uid, title=title, description=body or title))
                count += 1
            await session.commit()
    except Exception as exc:
        logger.error("Broadcast failed: %s", exc)
        await message.answer(get_text(lang, "db_error"))
        return

    await message.answer(
        get_text(lang, "broadcast_sent").replace("{count}", str(count))
    )


# ── Cashout management ────────────────────────────────────────────────────────

async def _send_cashouts_page(target, lang: str, page: int, send_new: bool = False) -> None:
    try:
        async with AsyncSessionLocal() as session:
            total_count = await session.scalar(
                select(func.count(CashoutRequest.id)).where(
                    CashoutRequest.status == CashoutRequestStatus.PENDING
                )
            ) or 0
            result = await session.execute(
                select(CashoutRequest)
                .options(selectinload(CashoutRequest.user))
                .where(CashoutRequest.status == CashoutRequestStatus.PENDING)
                .order_by(CashoutRequest.created_at.asc())
                .limit(PAGE_SIZE)
                .offset(page * PAGE_SIZE)
            )
            cashouts = result.scalars().all()
    except Exception as exc:
        logger.error("DB error loading cashouts: %s", exc)
        err = get_text(lang, "db_error")
        if send_new:
            await target.answer(err)
        else:
            await target.message.answer(err)
        return

    title_text = f"<b>{get_text(lang, 'cashouts_title')}</b>\nPending: {total_count}\n"

    if not cashouts:
        text = title_text + "\n✅ " + get_text(lang, "no_cashouts")
        keyboard = [[InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")]]
    else:
        lines = [title_text]
        keyboard: list[list[InlineKeyboardButton]] = []
        for c in cashouts:
            uname = _h(c.user.username if c.user else "?")
            platform = _h(c.source_platform)
            preview = _h((c.details_text or "")[:50])
            lines.append(f"• #{c.id} @{uname} | {platform}\n  ↳ {preview}…")
            keyboard.append([
                InlineKeyboardButton(text=f"📋 #{c.id} — {_h(c.user.first_name if c.user else '')}",
                                     callback_data=f"cashout_view_{c.id}")
            ])

        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"manage_cashouts_{page - 1}"))
        if (page + 1) * PAGE_SIZE < total_count:
            nav.append(InlineKeyboardButton(text="➡️", callback_data=f"manage_cashouts_{page + 1}"))
        if nav:
            keyboard.append(nav)
        keyboard.append([InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")])
        text = "\n".join(lines)

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    if send_new:
        await target.answer(text=text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("manage_cashouts_"))
async def process_manage_cashouts(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    parts = callback.data.split("_")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _send_cashouts_page(callback, lang, page)
    await callback.answer()


# Legacy alias: old "tickets" button routes to cashouts
@admin_router.callback_query(F.data.startswith("manage_tickets"))
async def process_manage_tickets(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    await _send_cashouts_page(callback, lang, page=0)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("cashout_view_"))
async def view_cashout_detail(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    cashout_id = int(callback.data.removeprefix("cashout_view_"))

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CashoutRequest)
                .options(selectinload(CashoutRequest.user))
                .where(CashoutRequest.id == cashout_id)
            )
            c = result.scalars().first()
    except Exception as exc:
        logger.error("DB error in cashout_view: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    if not c:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return

    uname = _h(c.user.username if c.user else "?")
    fname = _h(c.user.first_name if c.user else "")
    platform = _h(c.source_platform)
    custom = _h(c.custom_source or "")
    details = _h(c.details_text or "")
    date = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "?"

    text = (
        f"💱 <b>Cashout Request #{cashout_id}</b>\n\n"
        f"👤 User: @{uname} {fname}\n"
        f"🌐 Platform: {platform}"
        + (f" ({custom})" if custom else "")
        + f"\n📅 Date: {date}\n\n"
        f"📝 Details:\n{details}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Mark Completed", callback_data=f"cashout_done_{cashout_id}"),
                InlineKeyboardButton(text="👁 Mark Reviewed", callback_data=f"cashout_review_{cashout_id}"),
            ],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_cashouts_0")],
        ]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("cashout_done_"))
async def cashout_mark_done(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    cashout_id = int(callback.data.removeprefix("cashout_done_"))
    await _update_cashout_status(callback, lang, cashout_id, CashoutRequestStatus.COMPLETED)


@admin_router.callback_query(F.data.startswith("cashout_review_"))
async def cashout_mark_reviewed(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    cashout_id = int(callback.data.removeprefix("cashout_review_"))
    await _update_cashout_status(callback, lang, cashout_id, CashoutRequestStatus.REVIEWED)


async def _update_cashout_status(
    callback: CallbackQuery, lang: str, cashout_id: int, new_status: CashoutRequestStatus
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            c = await session.get(CashoutRequest, cashout_id)
            if not c:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            c.status = new_status
            c.updated_at = utcnow()
            await session.commit()
    except Exception as exc:
        logger.error("Cashout status update failed: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    await callback.message.edit_text(
        f"✅ Cashout #{cashout_id} marked as <b>{_h(new_status.value)}</b>.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_cashouts_0")]]
        ),
        parse_mode="HTML",
    )
    await callback.answer(f"✅ Status updated to {new_status.value}", show_alert=False)


# ── Exchange rate management ──────────────────────────────────────────────────

def _rates_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ " + get_text(lang, "rates_btn"), callback_data="set_usdt_rate")],
            [InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")],
        ]
    )


@admin_router.callback_query(F.data == "manage_rates")
async def show_rates(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    rate = await get_usdt_rate()
    text = get_text(lang, "rates_info").format(rate=int(rate))
    await callback.message.edit_text(text=text, reply_markup=_rates_markup(lang), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "set_usdt_rate")
async def prompt_usdt_rate(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "enter_usdt_rate"), parse_mode="HTML")
    await state.set_state(AdminPanelStates.awaiting_usdt_rate)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_usdt_rate)
async def process_usdt_rate(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    raw = (message.text or "").strip().replace(",", "").replace("٬", "")

    if not raw.isdigit() or int(raw) <= 0:
        await message.answer(get_text(lang, "rate_invalid"))
        return

    new_rate = int(raw)
    await set_usdt_rate(new_rate)
    await state.clear()

    logger.info("Admin %s updated USDT rate to %d", message.from_user.id, new_rate)
    await message.answer(
        get_text(lang, "rate_updated").format(rate=new_rate),
        reply_markup=_rates_markup(lang),
        parse_mode="HTML",
    )
