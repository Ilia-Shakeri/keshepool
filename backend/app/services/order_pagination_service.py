import base64
import binascii
import re
import struct
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload

from app.models import Order


ORDER_PAGE_DEFAULT_LIMIT = 20
ORDER_PAGE_MAX_LIMIT = 50
ORDER_NEXT_CURSOR_HEADER = "X-Next-Cursor"
_CURSOR_BYTES = struct.Struct(">qQ")
_CURSOR_PATTERN = re.compile(r"^[A-Za-z0-9_-]{22}$")
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_MAX_ORDER_ID = 2_147_483_647


class InvalidOrderCursor(ValueError):
    pass


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def encode_order_cursor(created_at: datetime, order_id: int) -> str:
    if not 0 < order_id <= _MAX_ORDER_ID:
        raise ValueError("Order cursor ID is outside the supported range.")
    created_utc = _as_utc(created_at)
    delta = created_utc - _EPOCH
    microseconds = (
        delta.days * 86_400_000_000
        + delta.seconds * 1_000_000
        + delta.microseconds
    )
    if microseconds < 0:
        raise ValueError("Order cursor timestamp is outside the supported range.")
    payload = _CURSOR_BYTES.pack(microseconds, order_id)
    return base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")


def decode_order_cursor(cursor: str) -> tuple[datetime, int]:
    if not _CURSOR_PATTERN.fullmatch(cursor):
        raise InvalidOrderCursor("Order cursor is malformed.")
    try:
        payload = base64.b64decode(cursor + "==", altchars=b"-_", validate=True)
        microseconds, order_id = _CURSOR_BYTES.unpack(payload)
        created_at = _EPOCH + timedelta(microseconds=microseconds)
    except (binascii.Error, OverflowError, struct.error, ValueError) as exc:
        raise InvalidOrderCursor("Order cursor is malformed.") from exc
    if microseconds < 0 or not 0 < order_id <= _MAX_ORDER_ID:
        raise InvalidOrderCursor("Order cursor is malformed.")
    return created_at, order_id


def build_user_order_page_statement(
    *,
    user_id: int,
    limit: int,
    cursor: tuple[datetime, int] | None,
):
    statement = (
        select(Order)
        .options(
            selectinload(Order.product),
            selectinload(Order.variant),
            selectinload(Order.inventory_item),
        )
        .where(Order.user_id == user_id)
    )
    if cursor is not None:
        created_at, order_id = cursor
        statement = statement.where(
            or_(
                Order.created_at < created_at,
                and_(Order.created_at == created_at, Order.id < order_id),
            )
        )
    return statement.order_by(Order.created_at.desc(), Order.id.desc()).limit(limit + 1)
