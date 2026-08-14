import asyncio
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile
from PIL import Image, PngImagePlugin

from app.api import payments
from app.models import (
    CardTransferAdminDelivery,
    CardTransferReceipt,
    Transaction,
    TransactionStatus,
    TransactionType,
    User,
    Wallet,
)
from app.services import card_transfer_service


def run(coroutine):
    return asyncio.run(coroutine)


def png_bytes(*, metadata: bool = False) -> bytes:
    image = Image.new("RGB", (96, 64), (20, 80, 160))
    output = io.BytesIO()
    pnginfo = None
    if metadata:
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("private", "remove-me")
    image.save(output, format="PNG", pnginfo=pnginfo)
    return output.getvalue()


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class FakeSession:
    def __init__(self, wallet):
        self.wallet = wallet
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, _statement):
        return FakeResult(self.wallet)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        transaction = next(value for value in self.added if isinstance(value, Transaction))
        transaction.id = 41

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_receipt_is_decoded_reencoded_and_metadata_free():
    receipt = card_transfer_service.sanitize_card_transfer_receipt(
        png_bytes(metadata=True)
    )

    assert receipt.mime_type == "image/jpeg"
    assert b"remove-me" not in receipt.image_bytes
    with Image.open(io.BytesIO(receipt.image_bytes)) as image:
        assert image.format == "JPEG"
        assert image.size == (96, 64)


@pytest.mark.parametrize("payload", [b"", b"not-an-image", b"\x89PNG\r\n"])
def test_receipt_rejects_empty_or_invalid_images(payload):
    with pytest.raises(card_transfer_service.CardTransferReceiptError):
        card_transfer_service.sanitize_card_transfer_receipt(payload)


def test_delivery_queue_targets_group_and_each_direct_admin(monkeypatch):
    monkeypatch.setattr(card_transfer_service.settings, "ADMIN_GROUP_CHAT_ID", "-100900")
    receipt = CardTransferReceipt(
        transaction_id=1,
        image_bytes=b"image",
        mime_type="image/jpeg",
        receipt_sha256="a" * 64,
    )

    card_transfer_service.queue_card_transfer_admin_deliveries(receipt)

    assert {delivery.chat_id for delivery in receipt.deliveries} == {
        "123456",
        "-100900",
    }


def test_card_transfer_creates_pending_transaction_receipt_and_delivery_queue(monkeypatch):
    monkeypatch.setattr(payments.settings, "ADMIN_GROUP_CHAT_ID", "-100900")
    monkeypatch.setattr(payments.settings, "CARD_TO_CARD_ENABLED", True)
    monkeypatch.setattr(
        payments,
        "check_rate_limit",
        AsyncMock(return_value=SimpleNamespace(backend_available=True, allowed=True)),
    )
    dispatch = AsyncMock()
    monkeypatch.setattr(payments, "dispatch_card_transfer_notifications", dispatch)
    wallet = SimpleNamespace(id=7)
    db = FakeSession(wallet)
    user = SimpleNamespace(id=3, telegram_id="991122")
    upload = UploadFile(filename="receipt.png", file=io.BytesIO(png_bytes()))
    background_tasks = BackgroundTasks()

    result = run(
        payments.create_card_transfer_deposit(
            amount=250_000,
            receipt=upload,
            background_tasks=background_tasks,
            user=user,
            db=db,
        )
    )

    transaction = next(value for value in db.added if isinstance(value, Transaction))
    stored_receipt = next(
        value for value in db.added if isinstance(value, CardTransferReceipt)
    )
    assert transaction.type == TransactionType.DEPOSIT_IRR
    assert transaction.status == TransactionStatus.PENDING
    assert transaction.gateway == "card_to_card"
    assert transaction.amount == 250_000
    assert stored_receipt.transaction_id == 41
    assert stored_receipt.mime_type == "image/jpeg"
    assert len(stored_receipt.deliveries) == 2
    assert result["adminDelivery"] == "queued"
    assert result["transactionId"] == 41
    assert db.commits == 1
    assert len(background_tasks.tasks) == 1
    assert background_tasks.tasks[0].func is dispatch
    assert background_tasks.tasks[0].args == (41,)


def test_tetra98_new_payment_is_disabled_before_database_work(monkeypatch):
    monkeypatch.setattr(payments.settings, "TETRA98_ENABLED", False)
    with pytest.raises(HTTPException) as error:
        run(
            payments.create_tetra98_payment(
                payments.Tetra98PaymentRequest(amount=100_000),
                SimpleNamespace(telegram_id="1"),
                FakeSession(SimpleNamespace(id=1)),
            )
        )
    assert error.value.status_code == 503


def test_card_transfer_models_have_replay_and_retry_guards():
    receipt_constraints = {
        constraint.name for constraint in CardTransferReceipt.__table__.constraints
    }
    delivery_constraints = {
        constraint.name
        for constraint in CardTransferAdminDelivery.__table__.constraints
    }
    delivery_indexes = {
        index.name for index in CardTransferAdminDelivery.__table__.indexes
    }
    assert "uq_card_transfer_receipts_sha256" in receipt_constraints
    assert "uq_card_transfer_receipts_transaction_id" in receipt_constraints
    assert "uq_card_transfer_delivery_receipt_chat" in delivery_constraints
    assert "ck_card_transfer_delivery_status" in delivery_constraints
    assert "ix_card_transfer_delivery_retry" in delivery_indexes


def test_admin_receipt_message_has_approve_and_reject_actions():
    user = User(telegram_id="991122", first_name="کاربر")
    wallet = Wallet(id=7, user=user)
    transaction = Transaction(
        id=41,
        wallet=wallet,
        wallet_id=7,
        amount=250_000,
        currency="IRR",
        type=TransactionType.DEPOSIT_IRR,
        status=TransactionStatus.PENDING,
        gateway="card_to_card",
    )
    receipt = CardTransferReceipt(
        transaction=transaction,
        transaction_id=41,
        image_bytes=b"image",
        mime_type="image/jpeg",
        receipt_sha256="b" * 64,
    )

    caption, markup = card_transfer_service._notification_payload(receipt)

    assert "#41" in caption
    assert markup is not None
    callbacks = {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    }
    assert callbacks == {
        "transaction_approve_prompt_41",
        "transaction_deny_prompt_41",
    }
