import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy.dialects import postgresql

from app.api import users
from app.models import ItemStatus, OrderStatus
from app.services.credential_access_service import MASKED_CREDENTIAL_PREVIEW
from app.services.order_pagination_service import (
    ORDER_NEXT_CURSOR_HEADER,
    InvalidOrderCursor,
    build_user_order_page_statement,
    decode_order_cursor,
    encode_order_cursor,
)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult(self.rows)


def run(coro):
    return asyncio.run(coro)


def order_row(order_id: int, created_at: datetime):
    return SimpleNamespace(
        id=order_id,
        public_id=f"KP-{order_id:032d}",
        user_id=7,
        status=OrderStatus.ACTIVE,
        created_at=created_at,
        expires_at=None,
        total_amount=100,
        credential_reveal_count=0,
        product=SimpleNamespace(
            title="Fixture product",
            brand="Fixture brand",
            asset_url=None,
            icon="Box",
            gradient="fixture",
        ),
        variant=SimpleNamespace(duration="Fixture duration"),
        inventory_item=SimpleNamespace(
            credentials="fixture-value",
            status=ItemStatus.ASSIGNED,
            assigned_to_user_id=7,
        ),
    )


def test_order_cursor_round_trip_is_fixed_length_and_microsecond_exact():
    created_at = datetime(2026, 8, 2, 13, 14, 15, 987654, tzinfo=timezone.utc)
    cursor = encode_order_cursor(created_at, 2_147_483_647)

    assert len(cursor) == 22
    assert decode_order_cursor(cursor) == (created_at, 2_147_483_647)


@pytest.mark.parametrize(
    "cursor",
    ["", "short", "!" * 22, "A" * 21, "A" * 23, "_" * 22],
)
def test_order_cursor_rejects_malformed_or_out_of_range_values(cursor):
    with pytest.raises(InvalidOrderCursor):
        decode_order_cursor(cursor)


def test_order_cursor_rejects_forged_64_bit_id():
    payload = b"\x00" * 8 + (2_147_483_648).to_bytes(8, "big")
    import base64

    cursor = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    with pytest.raises(InvalidOrderCursor):
        decode_order_cursor(cursor)


def test_order_page_sql_uses_stable_timestamp_and_id_tie_boundary():
    created_at = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    statement = build_user_order_page_statement(
        user_id=7,
        limit=20,
        cursor=(created_at, 42),
    )
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "orders.user_id = 7" in sql
    assert "orders.created_at <" in sql
    assert "orders.created_at =" in sql
    assert "orders.id < 42" in sql
    assert "ORDER BY orders.created_at DESC, orders.id DESC" in sql
    assert "LIMIT 21" in sql


def test_same_timestamp_pages_have_no_gap_or_overlap():
    tied_at = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    rows = [
        (tied_at + timedelta(seconds=1), 5),
        (tied_at, 9),
        (tied_at, 8),
        (tied_at, 7),
        (tied_at - timedelta(seconds=1), 20),
    ]
    ordered = sorted(rows, reverse=True)
    first_page = ordered[:3]
    cursor = decode_order_cursor(encode_order_cursor(*first_page[-1]))
    next_page = [row for row in ordered if row < cursor][:3]

    assert [row[1] for row in first_page] == [5, 9, 8]
    assert [row[1] for row in next_page] == [7, 20]
    assert set(first_page).isdisjoint(next_page)


def test_order_api_keeps_array_body_and_sets_next_cursor_header():
    tied_at = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    rows = [order_row(9, tied_at), order_row(8, tied_at), order_row(7, tied_at)]
    response = Response()

    payload = run(
        users.get_orders(
            response=response,
            cursor=None,
            limit=2,
            user=SimpleNamespace(id=7),
            db=FakeSession(rows),
        )
    )

    assert isinstance(payload, list)
    assert [row["id"] for row in payload] == [rows[0].public_id, rows[1].public_id]
    assert payload[0]["credentialPreview"] == MASKED_CREDENTIAL_PREVIEW
    assert "credentials" not in payload[0]
    assert decode_order_cursor(response.headers[ORDER_NEXT_CURSOR_HEADER]) == (tied_at, 8)


def test_order_api_rejects_invalid_cursor_before_database_access():
    session = FakeSession([])
    with pytest.raises(HTTPException) as raised:
        run(
            users.get_orders(
                response=Response(),
                cursor="A" * 22,
                limit=20,
                user=SimpleNamespace(id=7),
                db=session,
            )
        )

    assert raised.value.status_code == 422
    assert session.statements == []
