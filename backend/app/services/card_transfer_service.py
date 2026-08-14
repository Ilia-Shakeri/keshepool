import html
import io
import logging
import warnings
from dataclasses import dataclass
from datetime import timedelta

from aiogram import Bot
from aiogram.types import BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import (
    CardTransferAdminDelivery,
    CardTransferReceipt,
    Transaction,
    TransactionStatus,
    User,
    Wallet,
    utcnow,
)

logger = logging.getLogger(__name__)

MAX_IMAGE_WIDTH = 4096
MAX_IMAGE_HEIGHT = 4096
MAX_IMAGE_PIXELS = 16_000_000


class CardTransferReceiptError(ValueError):
    pass


@dataclass(frozen=True)
class SanitizedReceipt:
    image_bytes: bytes
    mime_type: str


@dataclass(frozen=True)
class DeliveryResult:
    sent: int
    pending: int
    failed: int

    @property
    def complete(self) -> bool:
        return self.pending == 0 and self.failed == 0


def _validate_dimensions(image: Image.Image) -> None:
    width, height = image.size
    if (
        width < 1
        or height < 1
        or width > MAX_IMAGE_WIDTH
        or height > MAX_IMAGE_HEIGHT
        or width * height > MAX_IMAGE_PIXELS
    ):
        raise CardTransferReceiptError("image_dimensions")


def sanitize_card_transfer_receipt(file_bytes: bytes) -> SanitizedReceipt:
    if not file_bytes or len(file_bytes) > settings.CARD_TRANSFER_MAX_RECEIPT_BYTES:
        raise CardTransferReceiptError("receipt_size")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(file_bytes)) as probe:
                if probe.format not in {"JPEG", "PNG", "WEBP"}:
                    raise CardTransferReceiptError("image_required")
                if getattr(probe, "n_frames", 1) != 1:
                    raise CardTransferReceiptError("image_required")
                _validate_dimensions(probe)
                probe.verify()

            with Image.open(io.BytesIO(file_bytes)) as source:
                _validate_dimensions(source)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                _validate_dimensions(oriented)
                if "A" in oriented.getbands() or (
                    oriented.mode == "P" and "transparency" in oriented.info
                ):
                    rgba = oriented.convert("RGBA")
                    clean = Image.new("RGB", rgba.size, "white")
                    clean.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    clean = oriented.convert("RGB")

            output = io.BytesIO()
            clean.save(
                output,
                format="JPEG",
                quality=90,
                optimize=True,
                progressive=True,
            )
    except CardTransferReceiptError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
        UnidentifiedImageError,
        ValueError,
    ) as exc:
        raise CardTransferReceiptError("image_required") from exc

    encoded = output.getvalue()
    if not encoded or len(encoded) > 5_000_000:
        raise CardTransferReceiptError("receipt_size")
    return SanitizedReceipt(image_bytes=encoded, mime_type="image/jpeg")


def queue_card_transfer_admin_deliveries(receipt: CardTransferReceipt) -> None:
    for chat_id in settings.card_transfer_notification_chat_ids:
        receipt.deliveries.append(
            CardTransferAdminDelivery(
                chat_id=chat_id,
                status="pending",
                attempts=0,
                next_attempt_at=utcnow(),
            )
        )


def _user_label(user: User | None) -> str:
    if user is None:
        return "—"
    display = " ".join(
        part.strip()
        for part in (user.first_name or "", user.last_name or "")
        if part.strip()
    )
    return html.escape(display or user.username or user.telegram_id)


def _status_label(status: TransactionStatus) -> str:
    return {
        TransactionStatus.PENDING: "⏳ در انتظار بررسی",
        TransactionStatus.SUCCESS: "✅ تایید و واریز شد",
        TransactionStatus.FAILED: "❌ رد شد",
    }[status]


def _notification_payload(
    receipt: CardTransferReceipt,
) -> tuple[str, InlineKeyboardMarkup | None]:
    transaction = receipt.transaction
    wallet = transaction.wallet if transaction else None
    user = wallet.user if wallet else None
    telegram_id = html.escape(user.telegram_id if user else "—")
    caption = (
        "💳 <b>رسید کارت‌به‌کارت جدید</b>\n\n"
        f"شناسه تراکنش: <code>#{transaction.id}</code>\n"
        f"کاربر: <b>{_user_label(user)}</b>\n"
        f"شناسه تلگرام: <code>{telegram_id}</code>\n"
        f"مبلغ: <b>{transaction.amount:,.0f} تومان</b>\n"
        f"وضعیت: <b>{_status_label(transaction.status)}</b>"
    )
    if transaction.status != TransactionStatus.PENDING:
        return caption, None
    return caption, InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ تایید و شارژ",
                    callback_data=f"transaction_approve_prompt_{transaction.id}",
                ),
                InlineKeyboardButton(
                    text="❌ رد رسید",
                    callback_data=f"transaction_deny_prompt_{transaction.id}",
                ),
            ]
        ]
    )


def _receipt_query():
    return select(CardTransferReceipt).options(
        selectinload(CardTransferReceipt.transaction)
        .selectinload(Transaction.wallet)
        .selectinload(Wallet.user),
        selectinload(CardTransferReceipt.deliveries),
    )


async def deliver_card_transfer_notifications(
    bot: Bot,
    *,
    transaction_id: int | None = None,
    limit: int = 20,
) -> DeliveryResult:
    now = utcnow()
    async with AsyncSessionLocal() as session:
        statement = (
            select(CardTransferAdminDelivery)
            .options(
                selectinload(CardTransferAdminDelivery.receipt)
                .selectinload(CardTransferReceipt.transaction)
                .selectinload(Transaction.wallet)
                .selectinload(Wallet.user)
            )
            .where(
                CardTransferAdminDelivery.status == "pending",
                CardTransferAdminDelivery.next_attempt_at <= now,
            )
            .order_by(CardTransferAdminDelivery.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        if transaction_id is not None:
            statement = statement.join(CardTransferReceipt).where(
                CardTransferReceipt.transaction_id == transaction_id
            )
        deliveries = list((await session.execute(statement)).scalars().all())
        for delivery in deliveries:
            receipt = delivery.receipt
            caption, markup = _notification_payload(receipt)
            try:
                message = await bot.send_photo(
                    chat_id=int(delivery.chat_id),
                    photo=BufferedInputFile(
                        receipt.image_bytes,
                        filename=f"card-transfer-{receipt.transaction_id}.jpg",
                    ),
                    caption=caption,
                    reply_markup=markup,
                    parse_mode="HTML",
                )
            except Exception as exc:
                delivery.attempts += 1
                delivery.last_error_code = type(exc).__name__[:100]
                if delivery.attempts >= settings.CARD_TRANSFER_ADMIN_NOTIFY_MAX_ATTEMPTS:
                    delivery.status = "failed"
                else:
                    delay_seconds = min(3600, 30 * (2 ** min(delivery.attempts - 1, 7)))
                    delivery.next_attempt_at = now + timedelta(seconds=delay_seconds)
                logger.warning(
                    "Card transfer receipt delivery failed for transaction %s and target %s: %s",
                    receipt.transaction_id,
                    delivery.chat_id,
                    type(exc).__name__,
                )
            else:
                delivery.status = "sent"
                delivery.attempts += 1
                delivery.message_id = message.message_id
                delivery.last_error_code = None
        await session.commit()

        counts = {"sent": 0, "pending": 0, "failed": 0}
        count_statement = select(CardTransferAdminDelivery.status).join(CardTransferReceipt)
        if transaction_id is not None:
            count_statement = count_statement.where(
                CardTransferReceipt.transaction_id == transaction_id
            )
        statuses = (await session.execute(count_statement)).scalars().all()
        for status in statuses:
            counts[status] += 1
        return DeliveryResult(**counts)


async def dispatch_card_transfer_notifications(transaction_id: int) -> None:
    bot = Bot(token=settings.ADMIN_BOT_TOKEN)
    try:
        await deliver_card_transfer_notifications(
            bot,
            transaction_id=transaction_id,
        )
    except Exception:
        logger.exception(
            "Immediate card transfer notification dispatch failed for transaction %s.",
            transaction_id,
        )
    finally:
        await bot.session.close()


async def refresh_card_transfer_notifications(
    bot: Bot,
    transaction_id: int,
) -> bool:
    async with AsyncSessionLocal() as session:
        receipt = (
            await session.execute(
                _receipt_query().where(CardTransferReceipt.transaction_id == transaction_id)
            )
        ).scalars().first()
        if receipt is None:
            return False
        caption, markup = _notification_payload(receipt)
        sent_deliveries = [
            delivery
            for delivery in receipt.deliveries
            if delivery.status == "sent" and delivery.message_id is not None
        ]

    for delivery in sent_deliveries:
        try:
            await bot.edit_message_caption(
                chat_id=int(delivery.chat_id),
                message_id=delivery.message_id,
                caption=caption,
                reply_markup=markup,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning(
                "Card transfer receipt status refresh failed for transaction %s and target %s: %s",
                transaction_id,
                delivery.chat_id,
                type(exc).__name__,
            )
    return True
