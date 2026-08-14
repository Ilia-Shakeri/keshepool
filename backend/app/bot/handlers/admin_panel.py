import html
import hashlib
import json
import logging
from decimal import Decimal
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    BufferedInputFile,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from redis.exceptions import RedisError
from sqlalchemy import func, insert, literal, select
from sqlalchemy.orm import selectinload

from app.bot.filters import HasAdminRoleFilter, IsAdminFilter
from app.bot.states import AdminPanelStates
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.services.admin_audit_service import add_admin_audit, record_admin_audit
from app.services.admin_authorization_service import (
    AdminAuthorizationError,
    approve_request,
    consume_action_nonce,
    consume_approved_request,
    create_approval_request,
    effective_roles,
    issue_action_nonce,
    require_action_role,
)
from app.services.cache_service import namespaced_key
from app.services.rate_service import (
    apply_usdt_rate_override_in_session,
    cache_usdt_rate_override,
    clear_usdt_rate_override,
    get_usdt_rate,
    set_usdt_rate,
)
from app.bot.services.daily_report_settings import (
    is_daily_report_enabled,
    toggle_daily_report,
)
from app.models import (
    AdminApprovalRequest,
    CashoutRequest,
    CashoutRequestStatus,
    Notification,
    Order,
    OrderStatus,
    Transaction,
    TransactionStatus,
    User,
    UsdtRateOverride,
    utcnow,
)
from app.bot.locales.translations import get_text

logger = logging.getLogger(__name__)

admin_router = Router()
admin_router.message.filter(IsAdminFilter())
admin_router.callback_query.filter(IsAdminFilter())

PAGE_SIZE = 8


async def _send_customer_message(telegram_id: str, text: str) -> None:
    customer_bot = Bot(token=settings.BOT_TOKEN)
    try:
        await customer_bot.send_message(chat_id=telegram_id, text=text)
    finally:
        await customer_bot.session.close()


async def get_admin_lang(user_id: int) -> str:
    try:
        lang = await redis_client.get(namespaced_key(f"admin-language:{user_id}"))
    except RedisError as exc:
        logger.warning("Admin language cache unavailable: %s", type(exc).__name__)
        return "fa"
    return lang or "fa"


def _h(text: object) -> str:
    """Escape arbitrary values for Telegram HTML parse mode."""
    return html.escape(str(text) if text is not None else "")


def _bounded_admin_message(raw_text: str | None) -> tuple[str, str] | None:
    lines = (raw_text or "").strip().splitlines()
    title = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else title
    if (
        not title
        or len(title) > 100
        or len(body) > 3500
        or any(ord(char) < 32 and char not in {"\n", "\t"} for char in f"{title}{body}")
    ):
        return None
    return title, body or title


def get_persistent_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 " + get_text(lang, "home_btn"))],
            [KeyboardButton(text=get_text(lang, "inventory_title"))],
            [KeyboardButton(text=get_text(lang, "users_title"))],
            [KeyboardButton(text=get_text(lang, "report_btn"))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_main_menu_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "users_title"), callback_data="manage_users_0")],
            [InlineKeyboardButton(text=get_text(lang, "inventory_title"), callback_data="manage_inventory")],
            [InlineKeyboardButton(text=get_text(lang, "cashouts_title"), callback_data="manage_cashouts_0")],
            [InlineKeyboardButton(text=get_text(lang, "transactions_title"), callback_data="manage_transactions")],
            [InlineKeyboardButton(text=get_text(lang, "stats_title"), callback_data="manage_stats")],
            [InlineKeyboardButton(text=get_text(lang, "report_btn"), callback_data="force_report")],
            [InlineKeyboardButton(text=get_text(lang, "daily_report_btn"), callback_data="manage_daily_report")],
            [InlineKeyboardButton(text=get_text(lang, "broadcast_title"), callback_data="broadcast_msg")],
            [InlineKeyboardButton(text=get_text(lang, "rates_btn"), callback_data="manage_rates")],
            [InlineKeyboardButton(text=get_text(lang, "toggle_lang"), callback_data="toggle_language")],
        ]
    )


def _back_markup(lang: str, callback_data: str = "main_menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data=callback_data)]
        ]
    )


async def build_report_text(lang: str) -> str:
    """Build a detailed operational report for the instant report workflow."""
    report_timezone = ZoneInfo(settings.TZ)
    now_local = datetime.now(report_timezone)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    async with AsyncSessionLocal() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        new_today = await session.scalar(
            select(func.count(User.id)).where(User.created_at >= today_start)
        ) or 0
        total_orders = await session.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.ACTIVE)
        ) or 0
        total_revenue = await session.scalar(
            select(func.sum(Order.total_amount)).where(Order.status == OrderStatus.ACTIVE)
        )
        total_revenue = Decimal(total_revenue) if total_revenue is not None else Decimal("0")
        pending_tx = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.PENDING)
        ) or 0
        try:
            pending_cashouts = await session.scalar(
                select(func.count(CashoutRequest.id)).where(CashoutRequest.status == CashoutRequestStatus.PENDING)
            ) or 0
        except Exception as exc:
            logger.warning("cashout_requests query failed (migration pending?): %s", exc)
            pending_cashouts = "N/A"

    now = now_local.strftime("%Y-%m-%d %H:%M %Z")
    return get_text(lang, "report_text").format(
        now=_h(now),
        total_users=f"{total_users:,}",
        new_today=f"{new_today:,}",
        active_orders=f"{total_orders:,}",
        revenue=f"{total_revenue:,.0f}",
        pending_transactions=pending_tx,
        pending_cashouts=pending_cashouts,
    )


# ── Entry points ──────────────────────────────────────────────────────────────

async def build_stats_text(lang: str) -> str:
    """Build a compact dashboard for the system stats workflow."""
    async with AsyncSessionLocal() as session:
        total_users = await session.scalar(select(func.count(User.id))) or 0
        total_orders = await session.scalar(select(func.count(Order.id))) or 0
        active_orders = await session.scalar(
            select(func.count(Order.id)).where(Order.status == OrderStatus.ACTIVE)
        ) or 0
        successful_transactions = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.SUCCESS)
        ) or 0
        pending_transactions = await session.scalar(
            select(func.count(Transaction.id)).where(Transaction.status == TransactionStatus.PENDING)
        ) or 0
        pending_cashouts = await session.scalar(
            select(func.count(CashoutRequest.id)).where(CashoutRequest.status == CashoutRequestStatus.PENDING)
        ) or 0

    return get_text(lang, "stats_text").format(
        title=get_text(lang, "stats_title"),
        users=f"{total_users:,}",
        orders=f"{total_orders:,}",
        active_orders=f"{active_orders:,}",
        successful_transactions=f"{successful_transactions:,}",
        pending_transactions=f"{pending_transactions:,}",
        pending_cashouts=f"{pending_cashouts:,}",
    )


@admin_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    lang = await get_admin_lang(message.from_user.id)
    await message.answer(
        text=get_text(lang, "main_menu"),
        reply_markup=get_main_menu_markup(lang),
        parse_mode="HTML",
    )
    if getattr(getattr(message, "chat", None), "type", "private") == "private":
        await message.answer(
            text=get_text(lang, "persistent_hint"),
            reply_markup=get_persistent_menu(lang),
        )


@admin_router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await message.answer(get_text(lang, "operation_cancelled"), reply_markup=get_main_menu_markup(lang))


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


@admin_router.message(F.text.func(lambda t: t and t.startswith("📦")), HasAdminRoleFilter("catalog"))
async def shortcut_inventory(message: Message, state: FSMContext):
    from app.bot.handlers.products_admin import show_product_management_menu
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await show_product_management_menu(message, lang, state, send_new=True)


@admin_router.message(F.text.func(lambda t: t and t.startswith("👥")), HasAdminRoleFilter("support"))
async def shortcut_users(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await _send_users_page(message, lang, page=0, send_new=True)


@admin_router.message(F.text.func(lambda t: t and t.startswith("📊")), HasAdminRoleFilter("auditor", "finance"))
async def shortcut_report(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    await state.clear()
    await message.answer(
        get_text(lang, "system_report_choose"),
        reply_markup=_system_report_range_markup(lang),
    )


# ── Language toggle ───────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "toggle_language")
async def process_toggle_language(callback: CallbackQuery):
    current = await get_admin_lang(callback.from_user.id)
    new_lang = "en" if current == "fa" else "fa"
    try:
        await redis_client.set(
            namespaced_key(f"admin-language:{callback.from_user.id}"),
            new_lang,
        )
    except RedisError as exc:
        logger.warning("Admin language cache write failed: %s", type(exc).__name__)
        await callback.answer(get_text(current, "cache_unavailable"), show_alert=True)
        return
    await callback.message.edit_text(
        text=get_text(new_lang, "main_menu"),
        reply_markup=get_main_menu_markup(new_lang),
        parse_mode="HTML",
    )
    if getattr(callback.message.chat, "type", "") == "private":
        await callback.message.answer(
            text=get_text(new_lang, "persistent_hint"),
            reply_markup=get_persistent_menu(new_lang),
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

@admin_router.callback_query(F.data == "manage_stats", HasAdminRoleFilter("auditor", "finance"))
async def show_stats(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        text = await build_stats_text(lang)
    except Exception as exc:
        logger.error("System stats workflow failed: %s", exc, exc_info=True)
        text = get_text(lang, "db_error")
    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")]]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "force_report", HasAdminRoleFilter("auditor", "finance"))
async def process_force_report(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    await callback.message.edit_text(
        get_text(lang, "system_report_choose"),
        reply_markup=_system_report_range_markup(lang),
    )
    await callback.answer()


def _daily_report_markup(lang: str, enabled: bool) -> InlineKeyboardMarkup:
    toggle_key = "daily_report_disable_btn" if enabled else "daily_report_enable_btn"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, toggle_key), callback_data="toggle_daily_report")],
            [InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")],
        ]
    )


async def _show_daily_report_settings(callback: CallbackQuery, lang: str) -> None:
    enabled = await is_daily_report_enabled()
    status_key = "daily_report_status_on" if enabled else "daily_report_status_off"
    await callback.message.edit_text(
        get_text(lang, "daily_report_settings").format(status=get_text(lang, status_key)),
        reply_markup=_daily_report_markup(lang, enabled),
        parse_mode="HTML",
    )


@admin_router.callback_query(F.data == "manage_daily_report", HasAdminRoleFilter("auditor", "finance"))
async def manage_daily_report(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        await _show_daily_report_settings(callback, lang)
    except RedisError as exc:
        logger.warning("Daily report setting read failed: %s", type(exc).__name__)
        await callback.answer(get_text(lang, "cache_unavailable"), show_alert=True)
        return
    await callback.answer()


@admin_router.callback_query(F.data == "toggle_daily_report", HasAdminRoleFilter("superadmin"))
async def process_toggle_daily_report(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        enabled = await toggle_daily_report()
        await _show_daily_report_settings(callback, lang)
    except RedisError as exc:
        logger.warning("Daily report setting write failed: %s", type(exc).__name__)
        await callback.answer(get_text(lang, "cache_unavailable"), show_alert=True)
        return
    try:
        await record_admin_audit(
            actor_telegram_id=callback.from_user.id,
            action="daily_report.toggle",
            target_type="system_setting",
            target_id="daily_report",
            details={"enabled": enabled},
        )
    except Exception:
        logger.exception("Daily report toggle audit failed.")
    await callback.answer(get_text(lang, "daily_report_enabled" if enabled else "daily_report_disabled"))


def _system_report_range_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "report_today_btn"), callback_data="system_report_range_today")],
            [InlineKeyboardButton(text=get_text(lang, "report_7_days_btn"), callback_data="system_report_range_7d")],
            [InlineKeyboardButton(text=get_text(lang, "report_30_days_btn"), callback_data="system_report_range_30d")],
            [InlineKeyboardButton(text=get_text(lang, "report_all_time_btn"), callback_data="system_report_range_all")],
            [InlineKeyboardButton(text=get_text(lang, "report_custom_btn"), callback_data="system_report_range_custom")],
            [InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")],
        ]
    )


def _system_report_period(preset: str) -> tuple[datetime, datetime]:
    today = datetime.now(timezone.utc).date()
    end = datetime.combine(today + timedelta(days=1), time.min, timezone.utc)
    if preset == "today":
        start_date = today
    elif preset == "7d":
        start_date = today - timedelta(days=6)
    elif preset == "30d":
        start_date = today - timedelta(days=29)
    elif preset == "all":
        return datetime(1970, 1, 1, tzinfo=timezone.utc), end
    else:
        raise ValueError("Unknown report period.")
    return datetime.combine(start_date, time.min, timezone.utc), end


def _parse_system_report_range(raw: str) -> tuple[datetime, datetime]:
    parts = raw.split()
    if len(parts) != 2:
        raise ValueError("Two dates are required.")
    start_date, end_date = (date.fromisoformat(value) for value in parts)
    if start_date > end_date or (end_date - start_date).days > 3660:
        raise ValueError("Invalid report range.")
    return (
        datetime.combine(start_date, time.min, timezone.utc),
        datetime.combine(end_date + timedelta(days=1), time.min, timezone.utc),
    )


async def _send_system_report(
    target: Message,
    *,
    actor_telegram_id: int,
    lang: str,
    start: datetime,
    end: datetime,
) -> None:
    from app.services.system_report_service import (
        collect_system_report,
        make_system_report_pdf,
    )

    start_label = start.date().isoformat()
    end_label = (end - timedelta(microseconds=1)).date().isoformat()
    async with AsyncSessionLocal() as session:
        report = await collect_system_report(session, start=start, end=end)
        await add_admin_audit(
            session,
            actor_telegram_id=actor_telegram_id,
            action="system_report.pdf",
            target_type="report",
            target_id=f"{start_label}:{end_label}",
            details={"language": lang, "format": "pdf"},
        )
        await session.commit()
    pdf = make_system_report_pdf(
        report,
        start_label=start_label,
        end_label=end_label,
        lang=lang,
    )
    await target.answer_document(
        BufferedInputFile(
            pdf,
            filename=f"keshepool-report-{start_label}-{end_label}.pdf",
        ),
        caption=get_text(lang, "system_report_ready"),
    )


@admin_router.callback_query(F.data.startswith("system_report_range_"), HasAdminRoleFilter("auditor", "finance"))
async def system_report_range(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    preset = callback.data.removeprefix("system_report_range_")
    if preset == "custom":
        await state.set_state(AdminPanelStates.awaiting_system_report_range)
        await callback.message.answer(
            get_text(lang, "system_report_custom_prompt"),
            reply_markup=ForceReply(selective=True),
            parse_mode="HTML",
        )
        await callback.answer()
        return
    try:
        start, end = _system_report_period(preset)
        await _send_system_report(
            callback.message,
            actor_telegram_id=callback.from_user.id,
            lang=lang,
            start=start,
            end=end,
        )
    except Exception as exc:
        logger.error("System PDF report failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "system_report_failed"), show_alert=True)
        return
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_system_report_range, HasAdminRoleFilter("auditor", "finance"))
async def custom_system_report_range(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    try:
        start, end = _parse_system_report_range(message.text or "")
    except ValueError:
        await message.answer(
            get_text(lang, "system_report_invalid_range"),
            reply_markup=ForceReply(selective=True),
        )
        return
    try:
        await _send_system_report(
            message,
            actor_telegram_id=message.from_user.id,
            lang=lang,
            start=start,
            end=end,
        )
    except Exception as exc:
        logger.error("Custom system PDF report failed: %s", exc, exc_info=True)
        await message.answer(get_text(lang, "system_report_failed"))
        return
    await state.clear()


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

    lines = [
        get_text(lang, "users_summary").format(
            title=get_text(lang, "users_title"),
            total=f"{total_users:,}",
        )
    ]
    user_buttons: list[InlineKeyboardButton] = []

    for u in users:
        balance = Decimal(u.wallet.balance) if u.wallet else Decimal("0")
        uname = _h(u.username or "—")
        fname = _h(u.first_name or "")
        access_icon = "🚫" if u.is_banned else "✅"
        lines.append(f"{access_icon} <code>{u.id}</code> @{uname} {fname} | <b>{balance:,.0f}</b>")
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
        nav.append(InlineKeyboardButton(text=get_text(lang, "previous_page"), callback_data=f"manage_users_{page - 1}"))
    if (page + 1) * PAGE_SIZE < total_users:
        nav.append(InlineKeyboardButton(text=get_text(lang, "next_page"), callback_data=f"manage_users_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append(
        [InlineKeyboardButton(text=get_text(lang, "search_user_title"), callback_data="search_user")]
    )
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if send_new:
        await target.answer(text=text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("manage_users_"), HasAdminRoleFilter("support"))
async def process_manage_users(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    parts = callback.data.split("_")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _send_users_page(callback, lang, page)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("user_detail_"), HasAdminRoleFilter("support"))
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

    balance = Decimal(user.wallet.balance) if user.wallet else Decimal("0")
    created = user.created_at.strftime("%Y-%m-%d") if user.created_at else "?"
    last_seen = user.last_seen_at.strftime("%Y-%m-%d %H:%M") if user.last_seen_at else "?"

    text = get_text(lang, "user_detail_text").format(
        name=f"{_h(user.first_name)} {_h(user.last_name or '')}".strip(),
        telegram_id=_h(user.telegram_id),
        username=_h(user.username or "N/A"),
        balance=f"{balance:,.0f}",
        orders=order_count,
        premium="✅" if user.is_premium else "—",
        role=_h(user.role),
        registered=created,
        last_seen=last_seen,
        access=get_text(lang, "user_access_banned" if user.is_banned else "user_access_active"),
    )

    access_button = get_text(lang, "unban_user_btn" if user.is_banned else "ban_user_btn")

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "notify_btn"), callback_data=f"notify_user_{user.id}")],
            [InlineKeyboardButton(text=get_text(lang, "orders_btn"), callback_data=f"user_orders_{user.id}")],
            [InlineKeyboardButton(text=access_button, callback_data=f"user_access_prompt_{user.id}")],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_users_0")],
        ]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("user_access_prompt_"), HasAdminRoleFilter("support"))
async def prompt_user_access_change(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    user_id = int(callback.data.removeprefix("user_access_prompt_"))
    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            target_roles = await effective_roles(session, user.telegram_id) if user is not None else frozenset()
    except Exception as exc:
        logger.error("User access prompt failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    if user is None:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return
    if target_roles and not user.is_banned:
        await callback.answer(get_text(lang, "cannot_ban_admin"), show_alert=True)
        return

    text_key = "confirm_unban_user" if user.is_banned else "confirm_ban_user"
    button_key = "confirm_unban_user_btn" if user.is_banned else "confirm_ban_user_btn"
    async with AsyncSessionLocal() as session:
        if settings.ADMIN_RBAC_ENABLED:
            await require_action_role(session, callback.from_user.id, "user.access_change")
        nonce = await issue_action_nonce(
            session,
            actor_telegram_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            action="user.access_change",
            target_type="user",
            target_id=user.id,
        )
        await session.commit()
    callback_prefix = "usrub" if user.is_banned else "usrbn"
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, button_key), callback_data=f"{callback_prefix}:{user.id}:{nonce}")],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data=f"user_detail_{user.id}")],
        ]
    )
    await callback.message.edit_text(
        get_text(lang, text_key).format(name=_h(user.first_name or user.username or user.telegram_id)),
        reply_markup=markup,
        parse_mode="HTML",
    )
    await callback.answer()


async def _set_user_ban(callback: CallbackQuery, user_id: int, banned: bool, nonce: str) -> None:
    lang = await get_admin_lang(callback.from_user.id)
    try:
        async with AsyncSessionLocal() as session:
            if settings.ADMIN_RBAC_ENABLED:
                await require_action_role(session, callback.from_user.id, "user.access_change")
            await consume_action_nonce(
                session,
                nonce=nonce,
                actor_telegram_id=callback.from_user.id,
                chat_id=callback.message.chat.id,
                action="user.access_change",
                target_type="user",
                target_id=user_id,
            )
            result = await session.execute(
                select(User).where(User.id == user_id).with_for_update()
            )
            user = result.scalars().first()
            if user is None:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            if banned and await effective_roles(session, user.telegram_id):
                await callback.answer(get_text(lang, "cannot_ban_admin"), show_alert=True)
                return
            user.is_banned = banned
            user.banned_at = utcnow() if banned else None
            user.banned_by = str(callback.from_user.id) if banned else None
            await add_admin_audit(
                session,
                actor_telegram_id=callback.from_user.id,
                action="user_ban" if banned else "user_unban",
                target_type="user",
                target_id=user.id,
                details={"telegram_id": user.telegram_id},
            )
            await session.commit()
    except AdminAuthorizationError:
        await callback.answer(get_text(lang, "cannot_ban_admin"), show_alert=True)
        return
    except Exception as exc:
        logger.error("User access update failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    await callback.message.edit_text(
        get_text(lang, "user_banned" if banned else "user_unbanned"),
        reply_markup=_back_markup(lang, f"user_detail_{user_id}"),
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("usrbn:"), HasAdminRoleFilter("support"))
async def confirm_user_ban(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        _, raw_user_id, nonce = callback.data.split(":", 2)
        user_id = int(raw_user_id)
    except (AttributeError, ValueError):
        await callback.answer(get_text(lang, "invalid_format"), show_alert=True)
        return
    await _set_user_ban(callback, user_id, True, nonce)


@admin_router.callback_query(F.data.startswith("usrub:"), HasAdminRoleFilter("support"))
async def confirm_user_unban(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        _, raw_user_id, nonce = callback.data.split(":", 2)
        user_id = int(raw_user_id)
    except (AttributeError, ValueError):
        await callback.answer(get_text(lang, "invalid_format"), show_alert=True)
        return
    await _set_user_ban(callback, user_id, False, nonce)


@admin_router.callback_query(F.data.startswith("user_orders_"), HasAdminRoleFilter("support"))
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
        text = get_text(lang, "no_orders_for_user")
    else:
        lines = [get_text(lang, "user_orders_title").format(count=len(orders))]
        for o in orders:
            product_name = _h(o.product.brand if o.product else "?")
            duration = _h(o.variant.duration if o.variant else "?")
            amount = Decimal(o.total_amount)
            date = o.created_at.strftime("%m/%d") if o.created_at else "?"
            icon = "✅" if o.status.value == "active" else "⛔"
            lines.append(
                f"{icon} {product_name} {duration} — "
                f"{amount:,.0f} {get_text(lang, 'toman_label')} — {date}"
            )
        text = "\n".join(lines)

    markup = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data=f"user_detail_{user_id}")]]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("notify_user_"), HasAdminRoleFilter("support"))
async def prompt_user_notification(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    user_id = int(callback.data.removeprefix("notify_user_"))
    await state.update_data(notify_target_user_id=user_id)
    await callback.message.answer(
        get_text(lang, "notification_prompt"),
        parse_mode="HTML",
        reply_markup=_back_markup(lang, f"user_detail_{user_id}"),
    )
    await state.set_state(AdminPanelStates.awaiting_notification_text)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_notification_text, HasAdminRoleFilter("support"))
async def process_user_notification(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    parsed_message = _bounded_admin_message(message.text)
    if parsed_message is None:
        await message.answer(get_text(lang, "admin_message_invalid"))
        return
    title, body = parsed_message

    data = await state.get_data()
    target_id = data.get("notify_target_user_id")
    if not target_id:
        await message.answer(get_text(lang, "target_user_lost"))
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
    await message.answer(
        get_text(lang, "notification_sent"),
        reply_markup=_back_markup(lang, f"user_detail_{target_id}"),
    )


# ── Search user ───────────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "search_user", HasAdminRoleFilter("support"))
async def prompt_search(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    await callback.message.answer(
        get_text(lang, "search_prompt") + "\n\n" + get_text(lang, "cancel_hint"),
        reply_markup=_back_markup(lang),
    )
    await state.set_state(AdminPanelStates.awaiting_search_query)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_search_query, HasAdminRoleFilter("support"))
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
        await message.answer(get_text(lang, "user_not_found"), reply_markup=_back_markup(lang))
        return

    for user in users:
        balance = Decimal(user.wallet.balance) if user.wallet else Decimal("0")
        text = get_text(lang, "search_result_text").format(
            name=f"{_h(user.first_name)} {_h(user.last_name or '')}".strip(),
            telegram_id=_h(user.telegram_id),
            username=_h(user.username or "N/A"),
            balance=f"{balance:,.0f}",
            role=_h(user.role),
            access=get_text(lang, "user_access_banned" if user.is_banned else "user_access_active"),
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text(lang, "view_detail"), callback_data=f"user_detail_{user.id}")],
                [InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")],
            ]
        )
        await message.answer(text=text, reply_markup=markup, parse_mode="HTML")


# ── Broadcast ─────────────────────────────────────────────────────────────────

@admin_router.callback_query(F.data == "broadcast_msg", HasAdminRoleFilter("support"))
async def prompt_broadcast(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    await callback.message.answer(get_text(lang, "broadcast_prompt"), reply_markup=_back_markup(lang))
    await state.set_state(AdminPanelStates.awaiting_broadcast_message)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_broadcast_message, HasAdminRoleFilter("support"))
async def process_broadcast(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    parsed_message = _bounded_admin_message(message.text)
    if parsed_message is None:
        await message.answer(get_text(lang, "admin_message_invalid"))
        return
    title, body = parsed_message

    try:
        async with AsyncSessionLocal() as session:
            count = int(await session.scalar(select(func.count(User.id))) or 0)
            digest = hashlib.sha256(
                json.dumps(
                    {"body": body or title, "title": title},
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            nonce = await issue_action_nonce(
                session,
                actor_telegram_id=message.from_user.id,
                chat_id=message.chat.id,
                action="broadcast.send",
                target_type="user_segment",
                target_id=digest,
            )
            await session.commit()
    except Exception as exc:
        logger.error("Broadcast preview failed: %s", exc)
        await message.answer(get_text(lang, "db_error"))
        return

    await state.update_data(
        broadcast_title=title,
        broadcast_body=body or title,
        broadcast_digest=digest,
        broadcast_nonce=nonce,
    )
    await state.set_state(AdminPanelStates.awaiting_broadcast_confirmation)
    preview = get_text(lang, "broadcast_preview").format(
        title=_h(title),
        body=_h(body or title),
        count=count,
    )
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "broadcast_confirm_btn"), callback_data="broadcast_confirm")],
            [InlineKeyboardButton(text=get_text(lang, "broadcast_cancel_btn"), callback_data="broadcast_cancel")],
        ]
    )
    await message.answer(preview, reply_markup=markup, parse_mode="HTML")


@admin_router.callback_query(F.data == "broadcast_cancel", HasAdminRoleFilter("support"))
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(get_text(lang, "operation_cancelled"), reply_markup=_back_markup(lang))
    await callback.answer()


@admin_router.callback_query(F.data == "broadcast_confirm", HasAdminRoleFilter("support"))
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    data = await state.get_data()
    title = str(data.get("broadcast_title") or "").strip()
    body = str(data.get("broadcast_body") or "").strip()
    digest = hashlib.sha256(
        json.dumps(
            {"body": body or title, "title": title},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    if not title:
        await state.clear()
        await callback.answer(get_text(lang, "target_user_lost"), show_alert=True)
        return

    try:
        async with AsyncSessionLocal() as session:
            if digest != data.get("broadcast_digest"):
                raise AdminAuthorizationError("Broadcast payload changed.")
            if settings.ADMIN_RBAC_ENABLED:
                await require_action_role(session, callback.from_user.id, "broadcast.send")
            await consume_action_nonce(
                session,
                nonce=str(data.get("broadcast_nonce", "")),
                actor_telegram_id=callback.from_user.id,
                chat_id=callback.message.chat.id,
                action="broadcast.send",
                target_type="user_segment",
                target_id=digest,
            )
            count = int(await session.scalar(select(func.count(User.id))) or 0)
            if count:
                created_at = utcnow()
                statement = insert(Notification).from_select(
                    ["user_id", "title", "description", "is_read", "created_at"],
                    select(
                        User.id,
                        literal(title),
                        literal(body or title),
                        literal(False),
                        literal(created_at),
                    ),
                )
                await session.execute(statement)
            await add_admin_audit(
                session,
                actor_telegram_id=callback.from_user.id,
                action="broadcast.create",
                target_type="user_segment",
                target_id="all",
                details={"recipient_count": count},
                new_values={"title_length": len(title), "body_length": len(body or title)},
            )
            await session.commit()
    except AdminAuthorizationError:
        await callback.answer(get_text(lang, "operation_cancelled"), show_alert=True)
        return
    except Exception as exc:
        logger.error("Broadcast failed: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        get_text(lang, "broadcast_sent").replace("{count}", str(count)),
        reply_markup=_back_markup(lang),
    )
    await callback.answer()


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
        logger.error("DB error loading cashouts (table may need migration): %s", exc, exc_info=True)
        err = get_text(lang, "db_error")
        if send_new:
            await target.answer(err)
        else:
            try:
                await target.message.edit_text(err)
            except Exception:
                await target.message.answer(err)
        return

    title_text = get_text(lang, "cashout_summary").format(
        title=get_text(lang, "cashouts_title"),
        count=total_count,
    )

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
            nav.append(InlineKeyboardButton(text=get_text(lang, "previous_page"), callback_data=f"manage_cashouts_{page - 1}"))
        if (page + 1) * PAGE_SIZE < total_count:
            nav.append(InlineKeyboardButton(text=get_text(lang, "next_page"), callback_data=f"manage_cashouts_{page + 1}"))
        if nav:
            keyboard.append(nav)
        keyboard.append([InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")])
        text = "\n".join(lines)

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    if send_new:
        await target.answer(text=text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("manage_cashouts_"), HasAdminRoleFilter("finance", "support"))
async def process_manage_cashouts(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    parts = callback.data.split("_")
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    await _send_cashouts_page(callback, lang, page)
    await callback.answer()


# Legacy alias: old "tickets" button routes to cashouts
@admin_router.callback_query(F.data.startswith("manage_tickets"), HasAdminRoleFilter("finance", "support"))
async def process_manage_tickets(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    await _send_cashouts_page(callback, lang, page=0)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("cashout_view_"), HasAdminRoleFilter("finance", "support"))
async def view_cashout_detail(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    cashout_id = int(callback.data.removeprefix("cashout_view_"))
    complete_nonce = ""
    review_nonce = ""

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CashoutRequest)
                .options(selectinload(CashoutRequest.user))
                .where(CashoutRequest.id == cashout_id)
            )
            c = result.scalars().first()
            if c is not None:
                complete_nonce = await issue_action_nonce(
                    session,
                    actor_telegram_id=callback.from_user.id,
                    chat_id=callback.message.chat.id,
                    action="cashout.status_change",
                    target_type="cashout_request",
                    target_id=f"{cashout_id}:completed",
                )
                review_nonce = await issue_action_nonce(
                    session,
                    actor_telegram_id=callback.from_user.id,
                    chat_id=callback.message.chat.id,
                    action="cashout.status_change",
                    target_type="cashout_request",
                    target_id=f"{cashout_id}:reviewed",
                )
                await session.commit()
    except Exception as exc:
        logger.error("DB error in cashout_view: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    if not c:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return

    uname = _h(c.user.username if c.user else "?")
    fname = _h(c.user.first_name if c.user else "")
    lname = _h(c.user.last_name if c.user else "")
    telegram_id = _h(c.user.telegram_id if c.user else "?")
    app_user_id = _h(c.user.id if c.user else "?")
    platform = _h(c.source_platform)
    custom = _h(c.custom_source or "")
    details = _h(c.details_text or "")
    status = _h(
        get_text(lang, f"cashout_status_{c.status.value}") if c.status else "?"
    )
    date = c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "?"

    text = get_text(lang, "cashout_detail_text").format(
        id=cashout_id,
        app_user_id=app_user_id,
        telegram_id=telegram_id,
        username=uname,
        name=f"{fname} {lname}".strip(),
        platform=platform,
        custom=f" ({custom})" if custom else "",
        date=date,
        status=status,
        details=details,
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "cashout_private_btn"), callback_data=f"cashout_dm_{cashout_id}")],
            [InlineKeyboardButton(text=get_text(lang, "mark_done_btn"), callback_data=f"cashst:{cashout_id}:completed:{complete_nonce}")],
            [InlineKeyboardButton(text=get_text(lang, "mark_reviewed_btn"), callback_data=f"cashst:{cashout_id}:reviewed:{review_nonce}")],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_cashouts_0")],
        ]
    )
    await callback.message.edit_text(text=text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("cashout_dm_"), HasAdminRoleFilter("finance", "support"))
async def prompt_cashout_private_message(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    cashout_id = int(callback.data.removeprefix("cashout_dm_"))

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(CashoutRequest)
                .options(selectinload(CashoutRequest.user))
                .where(CashoutRequest.id == cashout_id)
            )
            cashout = result.scalars().first()
    except Exception as exc:
        logger.error("DB error before cashout private message: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    if not cashout or not cashout.user:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return

    await state.update_data(cashout_dm_user_telegram_id=cashout.user.telegram_id, cashout_dm_id=cashout_id)
    await callback.message.answer(
        get_text(lang, "cashout_private_prompt"),
        reply_markup=_back_markup(lang, f"cashout_view_{cashout_id}"),
    )
    await state.set_state(AdminPanelStates.awaiting_cashout_private_message)
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_cashout_private_message, HasAdminRoleFilter("finance", "support"))
async def process_cashout_private_message(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    data = await state.get_data()
    user_telegram_id = data.get("cashout_dm_user_telegram_id")
    text = (message.text or "").strip()

    if not user_telegram_id or not text:
        await message.answer(get_text(lang, "invalid_format"))
        return

    try:
        await _send_customer_message(user_telegram_id, text)
    except Exception as exc:
        logger.warning("Cashout private message delivery failed: %s", exc)
        cashout_id = data.get("cashout_dm_id")
        await message.answer(
            get_text(lang, "cashout_private_failed"),
            reply_markup=_back_markup(lang, f"cashout_view_{cashout_id}" if cashout_id else "manage_cashouts_0"),
        )
        await state.clear()
        return

    cashout_id = data.get("cashout_dm_id")
    await state.clear()
    await message.answer(
        get_text(lang, "cashout_private_sent"),
        reply_markup=_back_markup(lang, f"cashout_view_{cashout_id}" if cashout_id else "manage_cashouts_0"),
    )


@admin_router.callback_query(F.data.startswith("cashst:"), HasAdminRoleFilter("finance"))
async def change_cashout_status(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    try:
        _, raw_cashout_id, raw_status, nonce = callback.data.split(":", 3)
        cashout_id = int(raw_cashout_id)
        new_status = CashoutRequestStatus(raw_status)
        if new_status not in {CashoutRequestStatus.REVIEWED, CashoutRequestStatus.COMPLETED}:
            raise ValueError
    except (AttributeError, ValueError):
        await callback.answer(get_text(lang, "cashout_status_invalid"), show_alert=True)
        return
    await _update_cashout_status(callback, lang, cashout_id, new_status, nonce)


async def _update_cashout_status(
    callback: CallbackQuery,
    lang: str,
    cashout_id: int,
    new_status: CashoutRequestStatus,
    nonce: str,
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            if settings.ADMIN_RBAC_ENABLED:
                await require_action_role(session, callback.from_user.id, "cashout.status_change")
            await consume_action_nonce(
                session,
                nonce=nonce,
                actor_telegram_id=callback.from_user.id,
                chat_id=callback.message.chat.id,
                action="cashout.status_change",
                target_type="cashout_request",
                target_id=f"{cashout_id}:{new_status.value}",
            )
            result = await session.execute(
                select(CashoutRequest)
                .where(CashoutRequest.id == cashout_id)
                .with_for_update()
            )
            c = result.scalars().first()
            if not c:
                await callback.answer(get_text(lang, "not_found"), show_alert=True)
                return
            old_status = c.status
            if old_status == new_status:
                await callback.answer(get_text(lang, "cashout_status_unchanged"), show_alert=True)
                return
            allowed_transitions = {
                CashoutRequestStatus.PENDING: {
                    CashoutRequestStatus.REVIEWED,
                    CashoutRequestStatus.COMPLETED,
                },
                CashoutRequestStatus.REVIEWED: {CashoutRequestStatus.COMPLETED},
                CashoutRequestStatus.COMPLETED: set(),
            }
            if new_status not in allowed_transitions.get(old_status, set()):
                await callback.answer(get_text(lang, "cashout_status_invalid"), show_alert=True)
                return
            c.status = new_status
            c.updated_at = utcnow()
            user = await session.get(User, c.user_id)
            status_fa = (
                "تکمیل شد"
                if new_status == CashoutRequestStatus.COMPLETED
                else "در حال بررسی است"
            )
            session.add(
                Notification(
                    user_id=c.user_id,
                    title="به‌روزرسانی درخواست تسویه",
                    description=f"وضعیت درخواست تسویه شماره {cashout_id}: {status_fa}.",
                )
            )
            await add_admin_audit(
                session,
                actor_telegram_id=callback.from_user.id,
                action="cashout.status_change",
                target_type="cashout_request",
                target_id=cashout_id,
                details={"from_status": old_status.value, "to_status": new_status.value},
                old_values={"status": old_status.value},
                new_values={"status": new_status.value},
            )
            await session.commit()
    except AdminAuthorizationError:
        await callback.answer(get_text(lang, "cashout_status_invalid"), show_alert=True)
        return
    except Exception as exc:
        logger.error("Cashout status update failed: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    if user:
        try:
            await _send_customer_message(
                user.telegram_id,
                f"وضعیت درخواست تسویه شماره {cashout_id}: {status_fa}.",
            )
        except Exception:
            logger.exception("Cashout status message delivery failed for request %d", cashout_id)

    _status_labels = {
        CashoutRequestStatus.COMPLETED: {"fa": "تکمیل‌شده", "en": "completed"},
        CashoutRequestStatus.REVIEWED: {"fa": "بررسی‌شده", "en": "reviewed"},
    }
    status_label = _status_labels.get(new_status, {}).get(lang, new_status.value)
    await callback.message.edit_text(
        get_text(lang, "cashout_done_msg").format(id=cashout_id, status=_h(status_label)),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_cashouts_0")]]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


# ── Exchange rate management ──────────────────────────────────────────────────

def _rates_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "rate_edit_btn"), callback_data="set_usdt_rate")],
            [InlineKeyboardButton(text=get_text(lang, "rate_live_btn"), callback_data="clear_usdt_rate")],
            [InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")],
        ]
    )


@admin_router.callback_query(F.data == "manage_rates", HasAdminRoleFilter("finance"))
async def show_rates(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    rate = await get_usdt_rate()
    text = get_text(lang, "rates_info").format(rate=int(rate))
    await callback.message.edit_text(text=text, reply_markup=_rates_markup(lang), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "set_usdt_rate", HasAdminRoleFilter("finance"))
async def prompt_usdt_rate(callback: CallbackQuery, state: FSMContext):
    lang = await get_admin_lang(callback.from_user.id)
    async with AsyncSessionLocal() as session:
        if settings.ADMIN_RBAC_ENABLED:
            await require_action_role(session, callback.from_user.id, "rate.override")
        nonce = await issue_action_nonce(
            session,
            actor_telegram_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            action="rate.override",
            target_type="exchange_rate",
            target_id="USDT_IRR",
        )
        await session.commit()
    await state.update_data(rate_action_nonce=nonce)
    await callback.message.answer(
        get_text(lang, "enter_usdt_rate"),
        parse_mode="HTML",
        reply_markup=_back_markup(lang, "manage_rates"),
    )
    await state.set_state(AdminPanelStates.awaiting_usdt_rate)
    await callback.answer()


@admin_router.callback_query(F.data == "clear_usdt_rate", HasAdminRoleFilter("finance"))
async def prompt_clear_manual_usdt_rate(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    async with AsyncSessionLocal() as session:
        if settings.ADMIN_RBAC_ENABLED:
            await require_action_role(session, callback.from_user.id, "rate.override")
        nonce = await issue_action_nonce(
            session,
            actor_telegram_id=callback.from_user.id,
            chat_id=callback.message.chat.id,
            action="rate.override",
            target_type="exchange_rate",
            target_id="USDT_IRR",
        )
        await session.commit()
    await callback.message.edit_text(
        get_text(lang, "rate_clear_confirm"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=get_text(lang, "rate_clear_confirm_btn"),
                    callback_data=f"rateclr:{nonce}",
                )],
                [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_rates")],
            ]
        ),
    )
    await callback.answer()


def _rate_approval_snapshot(
    old_rate: int,
    new_rate: int | None,
    expected_version: int,
) -> str:
    return json.dumps(
        {"expected_version": expected_version, "new": new_rate, "old": old_rate},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _rate_change_needs_dual_approval(
    current_rate: int,
    new_rate: int,
    threshold_percent: int,
) -> bool:
    if current_rate <= 0 or new_rate <= 0 or threshold_percent <= 0:
        raise ValueError("Rate approval inputs must be positive.")
    deviation = (
        abs(Decimal(new_rate) - Decimal(current_rate)) * Decimal(100)
    ) / Decimal(current_rate)
    return deviation >= Decimal(threshold_percent)


async def _create_rate_approval(
    session,
    *,
    actor_id: int,
    old_rate: int,
    new_rate: int | None,
) -> AdminApprovalRequest:
    current_state = await session.get(
        UsdtRateOverride,
        1,
        with_for_update=True,
    )
    expected_version = int(current_state.version) if current_state is not None else 0
    snapshot = _rate_approval_snapshot(old_rate, new_rate, expected_version)
    request = await create_approval_request(
        session,
        actor_telegram_id=actor_id,
        action="rate.override",
        target_type="exchange_rate",
        target_id=snapshot,
        payload=snapshot.encode("ascii"),
    )
    await add_admin_audit(
        session,
        actor_telegram_id=actor_id,
        action="exchange_rate.approval_requested",
        target_type="exchange_rate",
        target_id="USDT_IRR",
        outcome="requested",
        old_values={"rate": old_rate},
        new_values={"rate": new_rate},
        details={"approval_request_id": request.id},
    )
    return request


async def _send_rate_approval_notice(bot: Bot, lang: str, request: AdminApprovalRequest) -> None:
    snapshot = json.loads(request.target_id)
    new_label = f"{snapshot['new']:,}" if snapshot["new"] is not None else get_text(lang, "rate_live_btn")
    await bot.send_message(
        chat_id=int(settings.ADMIN_GROUP_CHAT_ID),
        text=get_text(lang, "rate_dual_group_notice").format(old=snapshot["old"], new=new_label),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text=get_text(lang, "rate_dual_approve_btn"),
                callback_data=f"ratedual:{request.id}",
            )]]
        ),
        parse_mode="HTML",
    )


@admin_router.callback_query(F.data.startswith("rateclr:"), HasAdminRoleFilter("finance"))
async def clear_manual_usdt_rate(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    nonce = callback.data.removeprefix("rateclr:")
    try:
        current_rate = int(await get_usdt_rate())
        async with AsyncSessionLocal() as session:
            if settings.ADMIN_RBAC_ENABLED:
                await require_action_role(session, callback.from_user.id, "rate.override")
            await consume_action_nonce(
                session,
                nonce=nonce,
                actor_telegram_id=callback.from_user.id,
                chat_id=callback.message.chat.id,
                action="rate.override",
                target_type="exchange_rate",
                target_id="USDT_IRR",
            )
            request = None
            if settings.ADMIN_DUAL_APPROVAL_ENABLED:
                request = await _create_rate_approval(
                    session,
                    actor_id=callback.from_user.id,
                    old_rate=current_rate,
                    new_rate=None,
                )
            await session.commit()
        if request is not None:
            await _send_rate_approval_notice(callback.bot, lang, request)
            await callback.message.edit_text(get_text(lang, "rate_dual_pending"))
            await callback.answer()
            return
        await clear_usdt_rate_override(
            actor_telegram_id=callback.from_user.id,
            change_source="admin_bot",
        )
        if not settings.OPERATIONS_RATE_DB_ENABLED:
            await record_admin_audit(
                actor_telegram_id=callback.from_user.id,
                action="exchange_rate.return_to_live",
                target_type="exchange_rate",
                target_id="USDT_IRR",
                details={},
            )
    except Exception as exc:
        logger.error("Manual rate clear failed: %s", exc)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    logger.info("Admin %s returned USDT rate to live sources", callback.from_user.id)
    await callback.message.edit_text(
        get_text(lang, "rate_live_restored"),
        reply_markup=_rates_markup(lang),
    )
    await callback.answer()


@admin_router.message(AdminPanelStates.awaiting_usdt_rate, HasAdminRoleFilter("finance"))
async def process_usdt_rate(message: Message, state: FSMContext):
    lang = await get_admin_lang(message.from_user.id)
    raw = (message.text or "").strip().replace(",", "").replace("٬", "")

    if not raw.isdigit() or int(raw) <= 0:
        await message.answer(get_text(lang, "rate_invalid"))
        return

    new_rate = int(raw)
    try:
        current_rate = int(await get_usdt_rate())
        data = await state.get_data()
        async with AsyncSessionLocal() as session:
            if settings.ADMIN_RBAC_ENABLED:
                await require_action_role(session, message.from_user.id, "rate.override")
            await consume_action_nonce(
                session,
                nonce=str(data.get("rate_action_nonce", "")),
                actor_telegram_id=message.from_user.id,
                chat_id=message.chat.id,
                action="rate.override",
                target_type="exchange_rate",
                target_id="USDT_IRR",
            )
            request = None
            if (
                settings.ADMIN_DUAL_APPROVAL_ENABLED
                and _rate_change_needs_dual_approval(
                    current_rate,
                    new_rate,
                    settings.ADMIN_DUAL_APPROVAL_RATE_DEVIATION_PERCENT,
                )
            ):
                request = await _create_rate_approval(
                    session,
                    actor_id=message.from_user.id,
                    old_rate=current_rate,
                    new_rate=new_rate,
                )
            await session.commit()
        if request is not None:
            await state.clear()
            await _send_rate_approval_notice(message.bot, lang, request)
            await message.answer(get_text(lang, "rate_dual_pending"))
            return
        await set_usdt_rate(
            new_rate,
            actor_telegram_id=message.from_user.id,
            change_source="admin_bot",
        )
        if not settings.OPERATIONS_RATE_DB_ENABLED:
            await record_admin_audit(
                actor_telegram_id=message.from_user.id,
                action="exchange_rate.manual_override",
                target_type="exchange_rate",
                target_id="USDT_IRR",
                details={"rate": new_rate},
            )
    except Exception as exc:
        logger.error("Manual rate update failed: %s", exc)
        await message.answer(get_text(lang, "db_error"))
        return
    await state.clear()

    logger.info("Admin %s updated USDT rate to %d", message.from_user.id, new_rate)
    await message.answer(
        get_text(lang, "rate_updated").format(rate=new_rate),
        reply_markup=_rates_markup(lang),
        parse_mode="HTML",
    )


@admin_router.callback_query(F.data.startswith("ratedual:"), HasAdminRoleFilter("finance"))
async def approve_rate_change(callback: CallbackQuery):
    lang = await get_admin_lang(callback.from_user.id)
    if str(callback.message.chat.id) != str(settings.ADMIN_GROUP_CHAT_ID):
        await callback.answer(get_text(lang, "rate_invalid"), show_alert=True)
        return
    raw_request_id = callback.data.removeprefix("ratedual:")
    try:
        request_id = int(raw_request_id)
        async with AsyncSessionLocal() as session:
            request = await session.get(AdminApprovalRequest, request_id)
            if (
                request is None
                or request.action != "rate.override"
                or request.target_type != "exchange_rate"
            ):
                raise AdminAuthorizationError("Approval request rejected.")
            snapshot = json.loads(request.target_id)
            old_rate = int(snapshot["old"])
            new_rate = int(snapshot["new"]) if snapshot["new"] is not None else None
            expected_version = int(snapshot["expected_version"])
            if (
                old_rate <= 0
                or expected_version < 0
                or (new_rate is not None and new_rate <= 0)
            ):
                raise AdminAuthorizationError("Rate approval payload rejected.")
            current_state = await session.get(
                UsdtRateOverride,
                1,
                with_for_update=True,
            )
            current_version = int(current_state.version) if current_state is not None else 0
            if current_version != expected_version:
                raise AdminAuthorizationError("Rate changed before approval.")
            approved = await approve_request(
                session,
                approval_request_id=request_id,
                actor_telegram_id=callback.from_user.id,
                payload=request.target_id.encode("ascii"),
            )
            if not approved:
                raise AdminAuthorizationError("Second approval required.")
            await consume_approved_request(
                session,
                approval_request_id=request_id,
                action="rate.override",
                target_type="exchange_rate",
                target_id=request.target_id,
                payload=request.target_id.encode("ascii"),
            )
            state = await apply_usdt_rate_override_in_session(
                session,
                rate=new_rate,
                actor_telegram_id=callback.from_user.id,
                change_source="dual_approval",
            )
            await session.commit()
        await cache_usdt_rate_override(state)
    except (AdminAuthorizationError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        await record_admin_audit(
            actor_telegram_id=callback.from_user.id,
            action="exchange_rate.approval_rejected",
            target_type="approval_request",
            target_id=raw_request_id[:20],
            outcome="rejected",
            reason="invalid_or_replayed_approval",
        )
        await callback.answer(get_text(lang, "rate_invalid"), show_alert=True)
        return
    message_key = "rate_updated" if new_rate is not None else "rate_live_restored"
    message = get_text(lang, message_key)
    if new_rate is not None:
        message = message.format(rate=new_rate)
    await callback.message.edit_text(message, reply_markup=_rates_markup(lang), parse_mode="HTML")
    await callback.answer()
