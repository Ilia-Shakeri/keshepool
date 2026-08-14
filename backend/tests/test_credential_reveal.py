import asyncio
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Request, Response

from app.api import products, users
from sqlalchemy.dialects import postgresql

from app.models import AdminAuditLog, CredentialRevealEvent, ItemStatus, Order, OrderStatus
from app.services.cache_service import RateLimitDecision
from app.services.catalog_service import MAX_CREDENTIAL_LENGTH
from app.services.credential_access_service import MASKED_CREDENTIAL_PREVIEW


class FakeResult:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        if isinstance(self.value, list):
            return self.value[0] if self.value else None
        return self.value

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]

    def fetchall(self):
        return self.value if isinstance(self.value, list) else [self.value]

    def scalar_one_or_none(self):
        if isinstance(self.value, list):
            return self.value[0] if self.value else None
        return self.value


class FakeSession:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.commit_count = 0
        self.execute_count = 0
        self.statements = []

    async def execute(self, statement):
        self.execute_count += 1
        self.statements.append(statement)
        if not self.results:
            raise AssertionError(f"Unexpected database statement: {statement}")
        return FakeResult(self.results.pop(0))

    def add(self, row):
        self.added.append(row)

    async def flush(self):
        return None

    async def commit(self):
        self.commit_count += 1


def run(coro):
    return asyncio.run(coro)


def order_row(
    *,
    credential=None,
    status=OrderStatus.ACTIVE,
    owner_id=7,
    item_owner_id=7,
    reveal_count=0,
):
    value = credential if credential is not None else "fixture-" + "value"
    return SimpleNamespace(
        id=19,
        public_id="KP-0123456789ABCDEF0123456789ABCDEF",
        user_id=owner_id,
        status=status,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=None,
        total_amount=100,
        credential_reveal_count=reveal_count,
        product=SimpleNamespace(
            title="Fixture product",
            brand="Fixture brand",
            asset_url=None,
            icon="Box",
            gradient="from-gray-700 to-black",
        ),
        variant=SimpleNamespace(duration="Fixture duration"),
        inventory_item=SimpleNamespace(
            credentials=value,
            status=ItemStatus.ASSIGNED,
            assigned_to_user_id=item_owner_id,
        ),
    )


def request_with_id() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/orders/fixture/reveal-credential",
            "headers": [],
        }
    )
    request.state.request_id = "request-fixture-123"
    return request


def allowed_rate_limit() -> RateLimitDecision:
    return RateLimitDecision(allowed=True, count=1, backend_available=True)


def test_order_list_returns_mask_only_and_no_store_headers():
    order = order_row()
    response = Response()
    payload = run(
        users.get_orders(
            response=response,
            user=SimpleNamespace(id=7),
            db=FakeSession([[order]]),
        )
    )

    assert payload[0]["credentialPreview"] == MASKED_CREDENTIAL_PREVIEW
    assert payload[0]["credentialAvailable"] is True
    assert "credentials" not in payload[0]
    assert order.inventory_item.credentials not in json.dumps(payload)
    assert response.headers["Cache-Control"].startswith("no-store")
    assert response.headers["Pragma"] == "no-cache"


def test_default_response_models_have_no_plaintext_field():
    assert "credentials" not in users.UserOrderResponse.model_fields
    assert "credential" not in users.UserOrderResponse.model_fields
    assert "credentials" not in products.CheckoutOrderResponse.model_fields
    assert "credential" not in products.CheckoutOrderResponse.model_fields


def test_reveal_route_uses_fresh_user_dependency():
    route = next(
        route
        for route in users.router.routes
        if getattr(route, "path", "") == "/api/orders/{public_id}/reveal-credential"
    )
    assert users.current_fresh_user in {dependency.call for dependency in route.dependant.dependencies}


def test_owner_can_reveal_active_assigned_credential_with_audit(monkeypatch):
    order = order_row()
    session = FakeSession([order])
    response = Response()
    monkeypatch.setattr(users, "check_rate_limit", AsyncMock(return_value=allowed_rate_limit()))

    result = run(
        users.reveal_order_credential(
            request=request_with_id(),
            response=response,
            public_id=order.public_id,
            user=SimpleNamespace(id=7, telegram_id="700"),
            db=session,
        )
    )

    assert result.orderId == order.public_id
    assert result.credential == order.inventory_item.credentials
    audit = next(row for row in session.added if isinstance(row, AdminAuditLog))
    assert audit.action == "credential.reveal"
    assert audit.target_id == order.public_id
    assert audit.request_id == "request-fixture-123"
    assert audit.details == {"order_status": "active", "reveal_count": 1}
    assert order.inventory_item.credentials not in json.dumps(audit.details)
    event = next(row for row in session.added if isinstance(row, CredentialRevealEvent))
    assert event.outcome == "allowed"
    assert event.reveal_count == 1
    assert event.request_id == "request-fixture-123"
    assert order.credential_reveal_count == 1
    statement = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF orders" in statement
    assert session.commit_count == 1
    assert response.headers["Cache-Control"].startswith("no-store")
    assert response.headers["Expires"] == "0"


@pytest.mark.parametrize(
    ("decision", "status_code"),
    [
        (RateLimitDecision(allowed=False, count=11, backend_available=True), 429),
        (RateLimitDecision(allowed=True, count=None, backend_available=False), 503),
    ],
)
def test_reveal_fails_closed_before_database_access(monkeypatch, decision, status_code):
    session = FakeSession([])
    monkeypatch.setattr(users, "check_rate_limit", AsyncMock(return_value=decision))

    with pytest.raises(HTTPException) as raised:
        run(
            users.reveal_order_credential(
                request=request_with_id(),
                response=Response(),
                public_id="KP-0123456789ABCDEF0123456789ABCDEF",
                user=SimpleNamespace(id=7, telegram_id="700"),
                db=session,
            )
        )
    assert raised.value.status_code == status_code
    assert raised.value.headers["Cache-Control"].startswith("no-store")
    assert raised.value.headers["Pragma"] == "no-cache"
    assert session.execute_count == 0


@pytest.mark.parametrize(
    ("order", "expected_outcome"),
    [
        (None, "denied_not_found"),
        (order_row(status=OrderStatus.REFUNDED), "denied_state"),
        (order_row(item_owner_id=8), "denied_state"),
    ],
)
def test_reveal_records_non_owner_result_and_unavailable_state(monkeypatch, order, expected_outcome):
    monkeypatch.setattr(users, "check_rate_limit", AsyncMock(return_value=allowed_rate_limit()))
    session = FakeSession([order])

    with pytest.raises(HTTPException) as raised:
        run(
            users.reveal_order_credential(
                request=request_with_id(),
                response=Response(),
                public_id="KP-0123456789ABCDEF0123456789ABCDEF",
                user=SimpleNamespace(id=7, telegram_id="700"),
                db=session,
            )
    )
    assert raised.value.status_code == (404 if order is None else 409)
    event = next(row for row in session.added if isinstance(row, CredentialRevealEvent))
    assert event.outcome == expected_outcome
    assert event.order_id == (None if order is None else order.id)
    audit = next(row for row in session.added if isinstance(row, AdminAuditLog))
    assert audit.outcome == "rejected"
    assert audit.reason == expected_outcome
    assert session.commit_count == 1


def test_reveal_rejects_legacy_value_over_response_bound(monkeypatch):
    order = order_row(credential="x" * (MAX_CREDENTIAL_LENGTH + 1))
    monkeypatch.setattr(users, "check_rate_limit", AsyncMock(return_value=allowed_rate_limit()))
    session = FakeSession([order])

    with pytest.raises(HTTPException) as raised:
        run(
            users.reveal_order_credential(
                request=request_with_id(),
                response=Response(),
                public_id=order.public_id,
                user=SimpleNamespace(id=7, telegram_id="700"),
                db=session,
            )
    )
    assert raised.value.status_code == 409
    event = next(row for row in session.added if isinstance(row, CredentialRevealEvent))
    assert event.outcome == "denied_size"
    assert event.reveal_count == 0
    assert session.commit_count == 1


def test_reveal_limit_is_durable_and_checked_under_order_lock(monkeypatch):
    order = order_row(reveal_count=users.settings.CREDENTIAL_REVEAL_MAX_PER_ORDER)
    monkeypatch.setattr(users, "check_rate_limit", AsyncMock(return_value=allowed_rate_limit()))
    session = FakeSession([order])

    with pytest.raises(HTTPException) as raised:
        run(
            users.reveal_order_credential(
                request=request_with_id(),
                response=Response(),
                public_id=order.public_id,
                user=SimpleNamespace(id=7, telegram_id="700"),
                db=session,
            )
        )

    assert raised.value.status_code == 409
    assert order.credential_reveal_count == users.settings.CREDENTIAL_REVEAL_MAX_PER_ORDER
    event = next(row for row in session.added if isinstance(row, CredentialRevealEvent))
    assert event.outcome == "denied_limit"
    statement = str(session.statements[0].compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE OF orders" in statement
    assert session.commit_count == 1


def test_reveal_history_schema_has_no_plaintext_column():
    assert "credential" not in CredentialRevealEvent.__table__.c
    assert "credentials" not in CredentialRevealEvent.__table__.c


def test_revision_014_matches_bounded_reveal_model():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "014_credential_reveal_events.py"
    )
    spec = importlib.util.spec_from_file_location("migration_014", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    assert migration.revision == "014"
    assert migration.down_revision == "013"
    assert Order.__table__.c.credential_reveal_count.server_default is not None
    order_constraints = {constraint.name for constraint in Order.__table__.constraints}
    event_constraints = {
        constraint.name for constraint in CredentialRevealEvent.__table__.constraints
    }
    event_indexes = {index.name for index in CredentialRevealEvent.__table__.indexes}
    order_indexes = {index.name for index in Order.__table__.indexes}
    assert "ck_orders_credential_reveal_count" in order_constraints
    assert "ix_orders_user_created_id" in order_indexes
    assert {
        "ck_credential_reveal_event_outcome",
        "ck_credential_reveal_event_count",
    } <= event_constraints
    assert {
        "ix_credential_reveal_order_created",
        "ix_credential_reveal_user_created",
    } <= event_indexes


def test_checkout_returns_masked_metadata_without_plaintext(monkeypatch):
    order = order_row()
    order.snapshot_state = "complete"
    order.product_title_snapshot = "Frozen product"
    order.product_brand_snapshot = "Frozen brand"
    order.variant_duration_snapshot = "Frozen duration"
    order.total_amount_snapshot = 88
    order.product.title = "Changed product"
    order.product.brand = "Changed brand"
    order.variant.duration = "Changed duration"
    session = FakeSession([order])
    monkeypatch.setattr(products, "check_rate_limit", AsyncMock(return_value=allowed_rate_limit()))
    monkeypatch.setattr(products, "fulfill_wallet_order", AsyncMock(return_value=order))
    monkeypatch.setattr(products, "invalidate_catalog_cache", AsyncMock())
    response = Response()

    payload = run(
        products.checkout_with_wallet(
            payload=products.CheckoutRequest(
                product_id="product-fixture",
                variant_id="variant-fixture",
                idempotencyKey="idempotency-fixture",
            ),
            response=response,
            idempotency_header="idempotency-fixture",
            user=SimpleNamespace(id=7, telegram_id="700"),
            db=session,
        )
    )

    assert payload["order"]["credentialPreview"] == MASKED_CREDENTIAL_PREVIEW
    assert payload["order"]["credentialAvailable"] is True
    assert payload["order"]["productTitle"] == "Frozen product"
    assert payload["order"]["productBrand"] == "Frozen brand"
    assert payload["order"]["variantDuration"] == "Frozen duration"
    assert payload["order"]["totalAmount"] == 88.0
    assert "credentials" not in payload["order"]
    assert order.inventory_item.credentials not in json.dumps(payload)
    assert response.headers["Cache-Control"].startswith("no-store")
