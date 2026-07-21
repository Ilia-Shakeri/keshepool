import html
import logging
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.filters import IsAdminFilter
from app.bot.locales.translations import get_text
from app.bot.states import AdminPanelStates
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Notification, Transaction, TransactionStatus, TransactionType, User, Wallet
from app.services.admin_audit_service import add_admin_audit, record_admin_audit
from app.services.rate_service import get_usdt_rate
from app.services.transaction_report_service import make_transaction_pdf
from app.services.wallet_service import to_decimal

logger = logging.getLogger(__name__)

transactions_router = Router()
transactions_router.message.filter(IsAdminFilter())
transactions_router.callback_query.filter(IsAdminFilter())

PAGE_SIZE = 8
DEPOSIT_TYPES = (TransactionType.DEPOSIT_IRR, TransactionType.DEPOSIT_CRYPTO)


async def _lang(user_id: int) -> str:
    from app.bot.handlers.admin_panel import get_admin_lang

    return await get_admin_lang(user_id)


def _h(value: object) -> str:
    return html.escape(str(value) if value is not None else "")


def _local_zone() -> ZoneInfo:
    try:
        return ZoneInfo(settings.TZ)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _transaction_type(lang: str, value: TransactionType) -> str:
    return get_text(lang, f"transaction_type_{value.value}")


def _transaction_status(lang: str, value: TransactionStatus) -> str:
    return get_text(lang, f"transaction_status_{value.value}")


def _transactions_menu_markup(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "pending_transactions_btn"), callback_data="transactions_pending_0")],
            [InlineKeyboardButton(text=get_text(lang, "transaction_summary_btn"), callback_data="transaction_summary")],
            [InlineKeyboardButton(text=get_text(lang, "transaction_pdf_btn"), callback_data="transaction_report")],
            [InlineKeyboardButton(text=get_text(lang, "back_to_menu"), callback_data="main_menu")],
        ]
    )


async def _transaction_rows(start_utc: datetime | None = None, end_utc: datetime | None = None):
    async with AsyncSessionLocal() as session:
        statement = (
            select(Transaction)
            .options(selectinload(Transaction.wallet).selectinload(Wallet.user))
            .order_by(Transaction.created_at.desc())
        )
        if start_utc is not None:
            statement = statement.where(Transaction.created_at >= start_utc)
        if end_utc is not None:
            statement = statement.where(Transaction.created_at < end_utc)
        result = await session.execute(statement)
        return list(result.scalars().all())


def _summary_text(lang: str, transactions: list[Transaction]) -> str:
    counts = {status: 0 for status in TransactionStatus}
    totals: dict[str, Decimal] = {}
    for transaction in transactions:
        counts[transaction.status] += 1
        if transaction.status == TransactionStatus.SUCCESS:
            currency = transaction.currency.upper()
            totals[currency] = totals.get(currency, Decimal("0")) + Decimal(transaction.amount)
    total_lines = "\n".join(
        f"• {_h(currency)}: <b>{amount:,.2f}</b>"
        for currency, amount in sorted(totals.items())
    ) or get_text(lang, "transaction_no_success_total")
    return get_text(lang, "transaction_summary_text").format(
        total=len(transactions),
        pending=counts[TransactionStatus.PENDING],
        success=counts[TransactionStatus.SUCCESS],
        failed=counts[TransactionStatus.FAILED],
        totals=total_lines,
    )


@transactions_router.callback_query(F.data == "manage_transactions")
async def show_transactions_menu(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.clear()
    try:
        transactions = await _transaction_rows()
        text = _summary_text(lang, transactions)
    except Exception as exc:
        logger.error("Transaction menu failed: %s", exc, exc_info=True)
        text = get_text(lang, "db_error")
    await callback.message.edit_text(
        text,
        reply_markup=_transactions_menu_markup(lang),
        parse_mode="HTML",
    )
    await callback.answer()


async def _show_pending_page(callback: CallbackQuery, lang: str, page: int) -> None:
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Transaction)
                .options(selectinload(Transaction.wallet).selectinload(Wallet.user))
                .where(
                    Transaction.status == TransactionStatus.PENDING,
                    Transaction.type.in_(DEPOSIT_TYPES),
                )
                .order_by(Transaction.created_at.asc())
            )
            all_transactions = list(result.scalars().all())
    except Exception as exc:
        logger.error("Pending transaction list failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return

    page = max(0, page)
    transactions = all_transactions[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]
    keyboard: list[list[InlineKeyboardButton]] = []
    for transaction in transactions:
        user = transaction.wallet.user if transaction.wallet else None
        label = get_text(lang, "pending_transaction_item").format(
            id=transaction.id,
            amount=f"{Decimal(transaction.amount):,.2f}",
            currency=transaction.currency,
            user=(user.first_name or user.username or user.telegram_id) if user else "?",
        )
        keyboard.append(
            [InlineKeyboardButton(text=label[:64], callback_data=f"transaction_view_{transaction.id}")]
        )

    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=get_text(lang, "previous_page"), callback_data=f"transactions_pending_{page - 1}"))
    if (page + 1) * PAGE_SIZE < len(all_transactions):
        nav.append(InlineKeyboardButton(text=get_text(lang, "next_page"), callback_data=f"transactions_pending_{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_transactions")])
    text = get_text(lang, "pending_transactions_text").format(count=len(all_transactions))
    if not transactions:
        text += "\n\n" + get_text(lang, "no_pending_transactions")
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )
    await callback.answer()


@transactions_router.callback_query(F.data.startswith("transactions_pending_"))
async def show_pending_transactions(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    raw_page = callback.data.removeprefix("transactions_pending_")
    page = int(raw_page) if raw_page.isdigit() else 0
    await _show_pending_page(callback, lang, page)


@transactions_router.callback_query(F.data.startswith("transaction_view_"))
async def show_transaction_detail(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    raw_id = callback.data.removeprefix("transaction_view_")
    if not raw_id.isdigit():
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Transaction)
                .options(selectinload(Transaction.wallet).selectinload(Wallet.user))
                .where(Transaction.id == int(raw_id))
            )
            transaction = result.scalars().first()
    except Exception as exc:
        logger.error("Transaction detail failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    if transaction is None:
        await callback.answer(get_text(lang, "not_found"), show_alert=True)
        return

    user = transaction.wallet.user if transaction.wallet else None
    text = get_text(lang, "transaction_detail_text").format(
        id=transaction.id,
        user=_h((user.first_name or user.username or "—") if user else "—"),
        telegram_id=_h(user.telegram_id if user else "—"),
        type=_h(_transaction_type(lang, transaction.type)),
        status=_h(_transaction_status(lang, transaction.status)),
        amount=f"{Decimal(transaction.amount):,.2f}",
        currency=_h(transaction.currency),
        gateway=_h(transaction.gateway or "—"),
        reference=_h(transaction.reference_id or "—"),
        date=_h(transaction.created_at.astimezone(_local_zone()).strftime("%Y-%m-%d %H:%M")),
    )
    keyboard: list[list[InlineKeyboardButton]] = []
    if transaction.status == TransactionStatus.PENDING and transaction.type in DEPOSIT_TYPES:
        keyboard.extend(
            [
                [InlineKeyboardButton(text=get_text(lang, "approve_transaction_btn"), callback_data=f"transaction_approve_prompt_{transaction.id}")],
                [InlineKeyboardButton(text=get_text(lang, "deny_transaction_btn"), callback_data=f"transaction_deny_prompt_{transaction.id}")],
            ]
        )
    keyboard.append([InlineKeyboardButton(text=get_text(lang, "back"), callback_data="transactions_pending_0")])
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )
    await callback.answer()


async def _confirmation(callback: CallbackQuery, lang: str, transaction_id: int, approve: bool) -> None:
    key = "confirm_approve_transaction" if approve else "confirm_deny_transaction"
    action = "approve" if approve else "deny"
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, f"confirm_{action}_transaction_btn"), callback_data=f"transaction_{action}_confirm_{transaction_id}")],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data=f"transaction_view_{transaction_id}")],
        ]
    )
    await callback.message.edit_text(
        get_text(lang, key).format(id=transaction_id),
        reply_markup=markup,
        parse_mode="HTML",
    )
    await callback.answer()


@transactions_router.callback_query(F.data.startswith("transaction_approve_prompt_"))
async def prompt_approve_transaction(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    await _confirmation(callback, lang, int(callback.data.removeprefix("transaction_approve_prompt_")), True)


@transactions_router.callback_query(F.data.startswith("transaction_deny_prompt_"))
async def prompt_deny_transaction(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    await _confirmation(callback, lang, int(callback.data.removeprefix("transaction_deny_prompt_")), False)


async def _approve_transaction(transaction_id: int, actor_id: int) -> Decimal:
    async with AsyncSessionLocal() as lookup_session:
        transaction = await lookup_session.get(Transaction, transaction_id)
        if transaction is None or transaction.status != TransactionStatus.PENDING:
            raise ValueError("not_pending")
        if transaction.type not in DEPOSIT_TYPES:
            raise ValueError("not_deposit")
        wallet_id = transaction.wallet_id
        rate = Decimal(str(await get_usdt_rate())) if transaction.type == TransactionType.DEPOSIT_CRYPTO else None

    async with AsyncSessionLocal() as session:
        wallet = (
            await session.execute(select(Wallet).where(Wallet.id == wallet_id).with_for_update())
        ).scalars().first()
        transaction = (
            await session.execute(select(Transaction).where(Transaction.id == transaction_id).with_for_update())
        ).scalars().first()
        if wallet is None or transaction is None:
            raise ValueError("not_found")
        if transaction.status != TransactionStatus.PENDING:
            raise ValueError("not_pending")
        if transaction.type not in DEPOSIT_TYPES:
            raise ValueError("not_deposit")

        credit = Decimal(transaction.amount)
        if rate is not None:
            credit *= rate
        credit = to_decimal(credit)
        wallet.balance = to_decimal(wallet.balance) + credit
        transaction.status = TransactionStatus.SUCCESS
        transaction.description = f"{transaction.description or ''} | Admin approved wallet credit: {credit} Toman".strip(" |")
        user = await session.get(User, wallet.user_id)
        if user is not None:
            user_lang = "fa" if (user.language_code or "fa").lower().startswith("fa") else "en"
            session.add(
                Notification(
                    user_id=user.id,
                    title=get_text(user_lang, "wallet_charge_result_title"),
                    description=get_text(user_lang, "wallet_charge_approved_user").format(amount=f"{credit:,.0f}"),
                )
            )
        await add_admin_audit(
            session,
            actor_telegram_id=actor_id,
            action="transaction_approve",
            target_type="transaction",
            target_id=transaction_id,
            details={"wallet_credit_toman": credit, "currency": transaction.currency},
        )
        await session.commit()
    return credit


@transactions_router.callback_query(F.data.startswith("transaction_approve_confirm_"))
async def approve_transaction(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    transaction_id = int(callback.data.removeprefix("transaction_approve_confirm_"))
    try:
        credit = await _approve_transaction(transaction_id, callback.from_user.id)
    except ValueError as exc:
        key = "transaction_not_pending" if str(exc) == "not_pending" else "transaction_cannot_review"
        await callback.answer(get_text(lang, key), show_alert=True)
        return
    except Exception as exc:
        logger.error("Transaction approval failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    await callback.message.edit_text(
        get_text(lang, "transaction_approved").format(id=transaction_id, amount=f"{credit:,.0f}"),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="transactions_pending_0")]]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@transactions_router.callback_query(F.data.startswith("transaction_deny_confirm_"))
async def deny_transaction(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    transaction_id = int(callback.data.removeprefix("transaction_deny_confirm_"))
    try:
        async with AsyncSessionLocal() as session:
            initial = await session.get(Transaction, transaction_id)
            if initial is None:
                raise ValueError("not_found")
            wallet = (
                await session.execute(select(Wallet).where(Wallet.id == initial.wallet_id).with_for_update())
            ).scalars().first()
            transaction = (
                await session.execute(select(Transaction).where(Transaction.id == transaction_id).with_for_update())
            ).scalars().first()
            if wallet is None or transaction is None:
                raise ValueError("not_found")
            if transaction.status != TransactionStatus.PENDING:
                raise ValueError("not_pending")
            if transaction.type not in DEPOSIT_TYPES:
                raise ValueError("not_deposit")
            transaction.status = TransactionStatus.FAILED
            transaction.description = f"{transaction.description or ''} | Admin denied wallet credit".strip(" |")
            user = await session.get(User, wallet.user_id)
            if user is not None:
                user_lang = "fa" if (user.language_code or "fa").lower().startswith("fa") else "en"
                session.add(
                    Notification(
                        user_id=user.id,
                        title=get_text(user_lang, "wallet_charge_result_title"),
                        description=get_text(user_lang, "wallet_charge_denied_user"),
                    )
                )
            await add_admin_audit(
                session,
                actor_telegram_id=callback.from_user.id,
                action="transaction_deny",
                target_type="transaction",
                target_id=transaction_id,
            )
            await session.commit()
    except ValueError as exc:
        key = "transaction_not_pending" if str(exc) == "not_pending" else "transaction_cannot_review"
        await callback.answer(get_text(lang, key), show_alert=True)
        return
    except Exception as exc:
        logger.error("Transaction denial failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    await callback.message.edit_text(
        get_text(lang, "transaction_denied").format(id=transaction_id),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="transactions_pending_0")]]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@transactions_router.callback_query(F.data == "transaction_summary")
async def show_transaction_summary(callback: CallbackQuery):
    lang = await _lang(callback.from_user.id)
    try:
        transactions = await _transaction_rows()
        text = _summary_text(lang, transactions)
    except Exception as exc:
        logger.error("Transaction summary failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "db_error"), show_alert=True)
        return
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_transactions")]]
        ),
        parse_mode="HTML",
    )
    await callback.answer()


@transactions_router.callback_query(F.data == "transaction_report")
async def choose_transaction_report_range(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    await state.clear()
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text(lang, "report_today_btn"), callback_data="transaction_report_range_today")],
            [InlineKeyboardButton(text=get_text(lang, "report_7_days_btn"), callback_data="transaction_report_range_7d")],
            [InlineKeyboardButton(text=get_text(lang, "report_30_days_btn"), callback_data="transaction_report_range_30d")],
            [InlineKeyboardButton(text=get_text(lang, "report_all_time_btn"), callback_data="transaction_report_range_all")],
            [InlineKeyboardButton(text=get_text(lang, "report_custom_btn"), callback_data="transaction_report_range_custom")],
            [InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_transactions")],
        ]
    )
    await callback.message.edit_text(get_text(lang, "transaction_report_choose"), reply_markup=markup)
    await callback.answer()


def _preset_range(preset: str) -> tuple[datetime, datetime]:
    zone = _local_zone()
    now_local = datetime.now(zone)
    end_local = now_local
    if preset == "today":
        start_local = datetime.combine(now_local.date(), time.min, tzinfo=zone)
    elif preset == "7d":
        start_local = now_local - timedelta(days=7)
    elif preset == "30d":
        start_local = now_local - timedelta(days=30)
    else:
        start_local = datetime(2000, 1, 1, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _normalize_digits(value: str) -> str:
    return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


async def _send_pdf(message: Message, actor_id: int, lang: str, start_utc: datetime, end_utc: datetime) -> None:
    transactions = await _transaction_rows(start_utc, end_utc)
    zone = _local_zone()
    rows: list[dict[str, object]] = []
    for transaction in transactions:
        user = transaction.wallet.user if transaction.wallet else None
        rows.append(
            {
                "id": transaction.id,
                "date": transaction.created_at.astimezone(zone).strftime("%Y-%m-%d %H:%M"),
                "user": (f"{user.telegram_id} @{user.username or '—'}" if user else "—"),
                "type": _transaction_type(lang, transaction.type),
                "status": _transaction_status(lang, transaction.status),
                "amount": f"{Decimal(transaction.amount):,.2f}",
                "currency": transaction.currency,
                "gateway": transaction.gateway or "—",
            }
        )
    start_label = start_utc.astimezone(zone).strftime("%Y-%m-%d")
    end_label = end_utc.astimezone(zone).strftime("%Y-%m-%d")
    pdf = make_transaction_pdf(
        rows,
        start_label=start_label,
        end_label=end_label,
        lang=lang,
    )
    await message.answer_document(
        BufferedInputFile(pdf, filename=f"transactions-{start_label}-{end_label}.pdf"),
        caption=get_text(lang, "transaction_report_ready").format(count=len(rows)),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="manage_transactions")]]
        ),
    )
    await record_admin_audit(
        actor_telegram_id=actor_id,
        action="transaction_report_pdf",
        target_type="transaction",
        details={"start": start_utc, "end": end_utc, "row_count": len(rows)},
    )


@transactions_router.callback_query(F.data.startswith("transaction_report_range_"))
async def transaction_report_range(callback: CallbackQuery, state: FSMContext):
    lang = await _lang(callback.from_user.id)
    preset = callback.data.removeprefix("transaction_report_range_")
    if preset == "custom":
        await state.set_state(AdminPanelStates.awaiting_transaction_report_range)
        await callback.message.edit_text(
            get_text(lang, "transaction_report_custom_prompt"),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="transaction_report")]]
            ),
        )
        await callback.answer()
        return
    try:
        start_utc, end_utc = _preset_range(preset)
        await _send_pdf(callback.message, callback.from_user.id, lang, start_utc, end_utc)
    except Exception as exc:
        logger.error("Transaction PDF failed: %s", exc, exc_info=True)
        await callback.answer(get_text(lang, "transaction_report_failed"), show_alert=True)
        return
    await callback.answer()


@transactions_router.message(AdminPanelStates.awaiting_transaction_report_range)
async def custom_transaction_report_range(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    parts = _normalize_digits((message.text or "").strip()).split()
    try:
        if len(parts) != 2:
            raise ValueError
        start_date = date.fromisoformat(parts[0])
        end_date = date.fromisoformat(parts[1])
        if start_date > end_date:
            raise ValueError
        zone = _local_zone()
        start_utc = datetime.combine(start_date, time.min, tzinfo=zone).astimezone(timezone.utc)
        end_utc = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    except ValueError:
        await message.answer(
            get_text(lang, "transaction_report_invalid_range"),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="transaction_report")]]
            ),
        )
        return
    try:
        await _send_pdf(message, message.from_user.id, lang, start_utc, end_utc)
    except Exception as exc:
        logger.error("Custom transaction PDF failed: %s", exc, exc_info=True)
        await message.answer(
            get_text(lang, "transaction_report_failed"),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=get_text(lang, "back"), callback_data="transaction_report")]]
            ),
        )
        return
    await state.clear()
