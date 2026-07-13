import asyncio
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from app.api import payments
from app.models import ItemStatus, TransactionStatus, TransactionType
from app.services import inventory_service


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


class FakeSession:
    def __init__(self, results, *, commit_error=None):
        self.results = list(results)
        self.commit_error = commit_error
        self.commit_count = 0
        self.rollback_count = 0
        self.added = []

    async def execute(self, statement):
        if not self.results:
            raise AssertionError(f"Unexpected database statement: {statement}")
        return FakeResult(self.results.pop(0))

    async def commit(self):
        self.commit_count += 1
        if self.commit_error:
            raise self.commit_error

    async def rollback(self):
        self.rollback_count += 1

    def add(self, value):
        self.added.append(value)

    async def refresh(self, value):
        return None


class FakeRequest:
    def __init__(self, payload, headers=None):
        self._body = json.dumps(payload).encode()
        self.headers = headers or {}

    async def body(self):
        return self._body

    async def form(self):
        return {}


class FakeHttpResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, json):
        return self.response


def crypto_transaction(**overrides):
    values = {
        "id": 7,
        "wallet_id": 3,
        "amount": Decimal("1.250000"),
        "currency": "USDT",
        "gateway": "crypto_wallet",
        "type": TransactionType.DEPOSIT_CRYPTO,
        "status": TransactionStatus.PENDING,
        "reference_id": "awaiting_confirmation",
        "description": "pending",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def tetra_transaction(**overrides):
    values = {
        "id": 9,
        "wallet_id": 4,
        "amount": Decimal("100000.00"),
        "currency": "IRR",
        "gateway": "tetra98",
        "type": TransactionType.DEPOSIT_IRR,
        "status": TransactionStatus.PENDING,
        "reference_id": "authority:auth_12345678",
        "description": "pending",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def run(coro):
    return asyncio.run(coro)


def test_usdt_amount_keeps_six_decimal_places():
    assert payments._usdt_amount("12.123456") == Decimal("12.123456")


def test_crypto_transaction_requires_exact_type_gateway_currency_reference_and_amount():
    payments._validate_pending_crypto_transaction(
        crypto_transaction(),
        Decimal("1.250000"),
    )

    for changes in (
        {"type": TransactionType.PURCHASE},
        {"gateway": "other"},
        {"currency": "IRR"},
        {"reference_id": "other"},
        {"amount": Decimal("1.250001")},
    ):
        with pytest.raises(HTTPException) as error:
            payments._validate_pending_crypto_transaction(
                crypto_transaction(**changes),
                Decimal("1.250000"),
            )
        assert error.value.status_code == 400


def test_missing_crypto_address_has_no_embedded_fallback(monkeypatch):
    monkeypatch.setattr(payments.settings, "CRYPTO_DEPOSIT_ADDRESS_USDT", "")
    with pytest.raises(HTTPException) as error:
        payments._usdt_trc20_deposit_address()
    assert error.value.status_code == 503


def test_configured_tetra_base_url_is_used(monkeypatch):
    monkeypatch.setattr(payments.settings, "TETRA98_API_URL", "https://pay.example.test/root/")
    assert payments._tetra98_url("api/verify") == "https://pay.example.test/root/api/verify"


def test_tetra_redirect_urls_are_https_and_bound_to_gateway_identity(monkeypatch):
    monkeypatch.setattr(payments.settings, "TETRA98_API_URL", "https://pay.example.test")
    authority = "auth_12345678"

    web_url = f"https://pay.example.test/payment/{authority}"
    bot_url = f"https://t.me/Tetra98_bot?start=pay_{authority}"
    assert payments._validated_tetra98_redirect_url(
        web_url,
        kind="web",
        authority=authority,
    ) == web_url
    assert payments._validated_tetra98_redirect_url(
        bot_url,
        kind="bot",
        authority=authority,
    ) == bot_url

    for bad_url, kind in (
        (f"http://pay.example.test/payment/{authority}", "web"),
        (f"https://evil.example/payment/{authority}", "web"),
        ("https://pay.example.test/payment/other", "web"),
        (f"https://evil.example/Tetra98_bot?start=pay_{authority}", "bot"),
        ("https://t.me/Tetra98_bot?start=pay_other", "bot"),
        ("https://t.me/Tetra98_bot?broken", "bot"),
    ):
        assert payments._validated_tetra98_redirect_url(
            bad_url,
            kind=kind,
            authority=authority,
        ) == ""


def test_tetra_authority_rejects_untrusted_gateway_values():
    assert payments._validated_tetra98_authority("auth_12345678") == "auth_12345678"
    assert payments._validated_tetra98_authority("https://evil.example") == ""
    assert payments._validated_tetra98_authority("short") == ""


def test_crypto_confirmation_commits_then_marks_processed():
    transaction = crypto_transaction()
    wallet = SimpleNamespace(id=3, user_id=22, balance=Decimal("500.00"))
    user = SimpleNamespace(id=22, telegram_id="22")
    db = FakeSession([transaction, wallet, transaction, None, user])
    reserve = AsyncMock(return_value=("token", False))
    release = AsyncMock()
    mark = AsyncMock()
    purchase = AsyncMock()

    with (
        patch.object(payments, "_reserve_crypto_webhook", reserve),
        patch.object(payments, "_release_crypto_webhook", release),
        patch.object(payments, "_mark_crypto_webhook_processed", mark),
        patch.object(payments, "get_usdt_rate", AsyncMock(return_value=Decimal("85000"))),
        patch.object(payments, "_try_auto_purchase", purchase),
    ):
        result = run(
            payments._process_crypto_confirmation(
                db,
                tx_id=7,
                tx_hash="abcdef1234567890",
                confirmed_amount=Decimal("1.250000"),
            )
        )

    assert result["status"] == "ok"
    assert db.commit_count == 1
    assert transaction.status == TransactionStatus.SUCCESS
    assert transaction.reference_id == "abcdef1234567890"
    assert wallet.balance == Decimal("106750.00")
    mark.assert_awaited_once_with("abcdef1234567890")
    release.assert_awaited_once_with("abcdef1234567890", "token")
    purchase.assert_awaited_once()


def test_crypto_commit_failure_clears_lock_and_allows_retry():
    transaction = crypto_transaction()
    wallet = SimpleNamespace(id=3, user_id=22, balance=Decimal("500.00"))
    failed_db = FakeSession(
        [transaction, wallet, transaction, None],
        commit_error=RuntimeError("database unavailable"),
    )
    release = AsyncMock()
    mark = AsyncMock()

    common_patches = (
        patch.object(payments, "_reserve_crypto_webhook", AsyncMock(return_value=("token", False))),
        patch.object(payments, "_release_crypto_webhook", release),
        patch.object(payments, "_mark_crypto_webhook_processed", mark),
        patch.object(payments, "get_usdt_rate", AsyncMock(return_value=Decimal("85000"))),
    )
    with common_patches[0], common_patches[1], common_patches[2], common_patches[3]:
        with pytest.raises(HTTPException) as error:
            run(
                payments._process_crypto_confirmation(
                    failed_db,
                    tx_id=7,
                    tx_hash="abcdef1234567890",
                    confirmed_amount=Decimal("1.250000"),
                )
            )

    assert error.value.status_code == 500
    assert failed_db.rollback_count == 1
    mark.assert_not_awaited()
    release.assert_awaited_once()

    transaction.status = TransactionStatus.PENDING
    transaction.reference_id = "awaiting_confirmation"
    wallet.balance = Decimal("500.00")
    retry_db = FakeSession([transaction, wallet, transaction, None, None])
    with (
        patch.object(payments, "_reserve_crypto_webhook", AsyncMock(return_value=("token2", False))),
        patch.object(payments, "_release_crypto_webhook", AsyncMock()),
        patch.object(payments, "_mark_crypto_webhook_processed", AsyncMock()),
        patch.object(payments, "get_usdt_rate", AsyncMock(return_value=Decimal("85000"))),
    ):
        result = run(
            payments._process_crypto_confirmation(
                retry_db,
                tx_id=7,
                tx_hash="abcdef1234567890",
                confirmed_amount=Decimal("1.250000"),
            )
        )
    assert result["status"] == "ok"
    assert retry_db.commit_count == 1


def test_processed_crypto_hash_short_circuits_without_database_work():
    db = FakeSession([])
    with patch.object(
        payments,
        "_reserve_crypto_webhook",
        AsyncMock(return_value=("unused", True)),
    ):
        result = run(
            payments._process_crypto_confirmation(
                db,
                tx_id=7,
                tx_hash="abcdef1234567890",
                confirmed_amount=Decimal("1.250000"),
            )
        )
    assert result["message"] == "Already processed."


def test_tetra_callback_validates_and_credits_exact_pending_transaction(monkeypatch):
    transaction = tetra_transaction()
    wallet = SimpleNamespace(id=4, user_id=33, balance=Decimal("100.00"))
    user = SimpleNamespace(id=33, telegram_id="33")
    db = FakeSession([transaction, wallet, transaction, None, user])
    request = FakeRequest(
        {"authority": "auth_12345678", "hashid": "9", "status": "100"}
    )
    response = FakeHttpResponse(
        {
            "status": "100",
            "hash_id": "9",
            "authority": "auth_12345678",
            "Amount": "1000000.00",
        }
    )
    monkeypatch.setattr(payments.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(payments.settings, "TETRA98_API_KEY", "test-key")
    monkeypatch.setattr(payments.settings, "TETRA98_WEBHOOK_SECRET", "")

    with (
        patch.object(payments.httpx, "AsyncClient", lambda **kwargs: FakeHttpClient(response)),
        patch.object(payments, "_try_auto_purchase", AsyncMock()),
        patch.object(payments, "_reserve_webhook", AsyncMock(return_value=("token", False))),
        patch.object(payments, "_release_webhook", AsyncMock()),
        patch.object(payments, "_mark_webhook_processed", AsyncMock()),
    ):
        result = run(payments.tetra98_payment_callback(request, db))

    assert result["status"] == "ok"
    assert db.commit_count == 1
    assert wallet.balance == Decimal("100100.00")
    assert transaction.status == TransactionStatus.SUCCESS
    assert transaction.reference_id == "auth_12345678"


def test_tetra_callback_rejects_wrong_transaction_kind_before_vendor_call(monkeypatch):
    transaction = tetra_transaction(type=TransactionType.PURCHASE)
    db = FakeSession([transaction])
    request = FakeRequest(
        {"authority": "auth_12345678", "hashid": "9", "status": "100"}
    )
    monkeypatch.setattr(payments.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(payments.settings, "TETRA98_API_KEY", "test-key")
    monkeypatch.setattr(payments.settings, "TETRA98_WEBHOOK_SECRET", "")

    with pytest.raises(HTTPException) as error:
        run(payments.tetra98_payment_callback(request, db))
    assert error.value.status_code == 400


def test_tetra_callback_duplicate_is_idempotent(monkeypatch):
    transaction = tetra_transaction(
        status=TransactionStatus.SUCCESS,
        reference_id="auth_12345678",
    )
    db = FakeSession([transaction])
    request = FakeRequest(
        {"authority": "auth_12345678", "hashid": "9", "status": "100"}
    )
    monkeypatch.setattr(payments.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(payments.settings, "TETRA98_API_KEY", "test-key")
    monkeypatch.setattr(payments.settings, "TETRA98_WEBHOOK_SECRET", "")

    result = run(payments.tetra98_payment_callback(request, db))
    assert result["message"] == "Already processed."
    assert db.commit_count == 0


def test_tetra_callback_rejects_verified_amount_mismatch(monkeypatch):
    transaction = tetra_transaction()
    db = FakeSession([transaction])
    request = FakeRequest(
        {"authority": "auth_12345678", "hashid": "9", "status": "100"}
    )
    response = FakeHttpResponse(
        {
            "status": "100",
            "hash_id": "9",
            "authority": "auth_12345678",
            "Amount": "999999.00",
        }
    )
    monkeypatch.setattr(payments.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(payments.settings, "TETRA98_API_KEY", "test-key")
    monkeypatch.setattr(payments.settings, "TETRA98_WEBHOOK_SECRET", "")

    with patch.object(
        payments.httpx,
        "AsyncClient",
        lambda **kwargs: FakeHttpClient(response),
    ):
        with pytest.raises(HTTPException) as error:
            run(payments.tetra98_payment_callback(request, db))

    assert error.value.status_code == 400
    assert db.commit_count == 0


def test_tetra_callback_accepts_official_verify_response_without_amount(monkeypatch):
    transaction = tetra_transaction()
    db = FakeSession([transaction])
    request = FakeRequest(
        {"authority": "auth_12345678", "hashid": "9", "status": "100"}
    )
    response = FakeHttpResponse(
        {
            "status": "100",
            "hash_id": "9",
            "authority": "auth_12345678",
        }
    )
    credit = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr(payments.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(payments.settings, "TETRA98_API_KEY", "test-key")
    monkeypatch.setattr(payments.settings, "TETRA98_WEBHOOK_SECRET", "")

    with (
        patch.object(payments.httpx, "AsyncClient", lambda **kwargs: FakeHttpClient(response)),
        patch.object(payments, "_credit_tetra98_transaction", credit),
    ):
        result = run(payments.tetra98_payment_callback(request, db))

    assert result == {"status": "ok"}
    assert db.commit_count == 0
    credit.assert_awaited_once_with(
        db,
        tx_id=9,
        wallet_id=4,
        authority="auth_12345678",
    )


@pytest.mark.parametrize(
    "verify_payload",
    [
        {"status": "100", "hash_id": "10", "authority": "auth_12345678"},
        {"status": "100", "hash_id": "9", "authority": "other_12345678"},
    ],
)
def test_tetra_callback_rejects_mismatched_verify_identity(monkeypatch, verify_payload):
    transaction = tetra_transaction()
    db = FakeSession([transaction])
    request = FakeRequest(
        {"authority": "auth_12345678", "hashid": "9", "status": "100"}
    )
    response = FakeHttpResponse(verify_payload)
    credit = AsyncMock()
    monkeypatch.setattr(payments.settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(payments.settings, "TETRA98_API_KEY", "test-key")
    monkeypatch.setattr(payments.settings, "TETRA98_WEBHOOK_SECRET", "")

    with (
        patch.object(payments.httpx, "AsyncClient", lambda **kwargs: FakeHttpClient(response)),
        patch.object(payments, "_credit_tetra98_transaction", credit),
    ):
        with pytest.raises(HTTPException) as error:
            run(payments.tetra98_payment_callback(request, db))

    assert error.value.status_code == 400
    credit.assert_not_awaited()


def test_tetra_credit_failure_releases_lock_for_retry():
    transaction = tetra_transaction()
    wallet = SimpleNamespace(id=4, user_id=33, balance=Decimal("100.00"))
    failed_db = FakeSession(
        [wallet, transaction, None],
        commit_error=RuntimeError("database unavailable"),
    )
    release = AsyncMock()
    mark = AsyncMock()
    with (
        patch.object(payments, "_reserve_webhook", AsyncMock(return_value=("token", False))),
        patch.object(payments, "_release_webhook", release),
        patch.object(payments, "_mark_webhook_processed", mark),
    ):
        with pytest.raises(HTTPException) as error:
            run(
                payments._credit_tetra98_transaction(
                    failed_db,
                    tx_id=9,
                    wallet_id=4,
                    authority="auth_12345678",
                )
            )

    assert error.value.status_code == 500
    assert failed_db.rollback_count == 1
    release.assert_awaited_once()
    mark.assert_not_awaited()

    transaction.status = TransactionStatus.PENDING
    transaction.reference_id = "authority:auth_12345678"
    wallet.balance = Decimal("100.00")
    retry_db = FakeSession([wallet, transaction, None, None])
    with (
        patch.object(payments, "_reserve_webhook", AsyncMock(return_value=("token2", False))),
        patch.object(payments, "_release_webhook", AsyncMock()),
        patch.object(payments, "_mark_webhook_processed", AsyncMock()),
    ):
        result = run(
            payments._credit_tetra98_transaction(
                retry_db,
                tx_id=9,
                wallet_id=4,
                authority="auth_12345678",
            )
        )
    assert result["status"] == "ok"
    assert retry_db.commit_count == 1


def test_production_callbacks_fail_closed_without_secrets(monkeypatch):
    monkeypatch.setattr(payments.settings, "ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as error:
        payments._require_production_webhook_secret("", "Crypto")
    assert error.value.status_code == 503


def test_checkout_idempotency_returns_same_order_without_second_sale():
    existing = SimpleNamespace(
        id=1,
        user_id=44,
        product_id="prod",
        variant_id="variant",
        idempotency_key="checkout-key-123",
    )
    db = FakeSession([existing])
    user = SimpleNamespace(id=44)

    order = run(
        inventory_service.fulfill_wallet_order(
            db,
            user,
            "prod",
            "variant",
            idempotency_key="checkout-key-123",
        )
    )

    assert order is existing
    assert db.commit_count == 0
    assert db.added == []


def test_checkout_rejects_reused_key_for_other_product():
    existing = SimpleNamespace(
        id=1,
        user_id=44,
        product_id="old-product",
        variant_id="old-variant",
        idempotency_key="checkout-key-123",
    )
    db = FakeSession([existing])
    user = SimpleNamespace(id=44)

    with pytest.raises(HTTPException) as error:
        run(
            inventory_service.fulfill_wallet_order(
                db,
                user,
                "new-product",
                "new-variant",
                idempotency_key="checkout-key-123",
            )
        )

    assert error.value.status_code == 409
    assert db.rollback_count == 1


def test_checkout_assigns_one_live_item_and_uses_long_public_id(monkeypatch):
    product = SimpleNamespace(id="prod", is_active=True, brand="Brand")
    variant = SimpleNamespace(
        id="variant",
        product_id="prod",
        is_active=True,
        product=product,
        raw_price=Decimal("250.00"),
        duration="1 month",
    )
    wallet = SimpleNamespace(id=2, user_id=44, balance=Decimal("1000.00"))
    item = SimpleNamespace(
        id=8,
        status=ItemStatus.AVAILABLE,
        assigned_to_user_id=None,
        assigned_at=None,
    )
    db = FakeSession([None, variant, wallet, None, None, item, None])
    user = SimpleNamespace(id=44)
    monkeypatch.setattr(inventory_service.secrets, "token_hex", lambda size: "a" * (size * 2))

    order = run(
        inventory_service.fulfill_wallet_order(
            db,
            user,
            "prod",
            "variant",
            idempotency_key="checkout-key-123",
        )
    )

    assert db.commit_count == 1
    assert wallet.balance == Decimal("750.00")
    assert item.status == ItemStatus.ASSIGNED
    assert item.assigned_to_user_id == 44
    assert order.idempotency_key == "checkout-key-123"
    assert order.public_id == f"KP-{'A' * 32}"
