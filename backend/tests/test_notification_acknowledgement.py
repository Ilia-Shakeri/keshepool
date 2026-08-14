import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from app.api import users
from app.services.cache_service import RateLimitDecision


@pytest.fixture(autouse=True)
def allow_notification_write_rate(monkeypatch):
    monkeypatch.setattr(
        users,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=1,
                backend_available=True,
            )
        ),
    )


class FakeResult:
    def __init__(self, value):
        self.value = value

    def fetchall(self):
        return self.value if isinstance(self.value, list) else [self.value]

    def scalar_one_or_none(self):
        if isinstance(self.value, list):
            return self.value[0] if self.value else None
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else [self.value]


class FakeSession:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []
        self.commit_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeResult(self.results.pop(0))

    async def commit(self):
        self.commit_count += 1


def run(coro):
    return asyncio.run(coro)


def compiled(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_one_notification_acknowledgement_is_owner_scoped():
    session = FakeSession([[17]])
    payload = run(
        users.mark_notification_read(
            notification_id=17,
            user=SimpleNamespace(id=7, telegram_id="700"),
            db=session,
        )
    )

    assert payload == {"marked": 1, "notificationId": 17}
    sql = compiled(session.statements[0])
    assert "notifications.id = 17" in sql
    assert "notifications.user_id = 7" in sql
    assert "notifications.is_read IS false" in sql
    assert session.commit_count == 1


def test_one_notification_acknowledgement_is_idempotent_for_owner():
    session = FakeSession([[], 17])
    payload = run(
        users.mark_notification_read(
            notification_id=17,
            user=SimpleNamespace(id=7, telegram_id="700"),
            db=session,
        )
    )

    assert payload == {"marked": 0, "notificationId": 17}
    assert session.commit_count == 0


def test_one_notification_acknowledgement_hides_other_owner():
    session = FakeSession([[], None])
    with pytest.raises(HTTPException) as raised:
        run(
            users.mark_notification_read(
                notification_id=17,
                user=SimpleNamespace(id=7, telegram_id="700"),
                db=session,
            )
        )

    assert raised.value.status_code == 404
    assert session.commit_count == 0


def test_bulk_acknowledgement_is_owner_scoped_and_bounded_through_id():
    session = FakeSession([[2, 5, 8]])
    payload = run(
        users.mark_notifications_read_through(
            payload=users.NotificationMarkReadThroughRequest(throughId=8),
            user=SimpleNamespace(id=7, telegram_id="700"),
            db=session,
        )
    )

    assert payload == {"marked": 3, "throughId": 8}
    sql = compiled(session.statements[0])
    assert "notifications.user_id = 7" in sql
    assert "notifications.id <= 8" in sql
    assert "notifications.is_read IS false" in sql
    assert session.commit_count == 1


def test_notification_list_is_stable_and_never_cacheable():
    notification = SimpleNamespace(
        id=8,
        title="Fixture",
        description="Fixture body",
        is_read=False,
        created_at=datetime(2026, 8, 2),
    )
    session = FakeSession([[notification]])
    response = Response()
    payload = run(
        users.get_notifications(
            response=response,
            user=SimpleNamespace(id=7, telegram_id="700"),
            db=session,
        )
    )

    assert payload[0]["id"] == 8
    sql = compiled(session.statements[0])
    assert "ORDER BY notifications.created_at DESC, notifications.id DESC" in sql
    assert response.headers["Cache-Control"].startswith("no-store")


def test_notification_write_rate_fails_closed_before_database(monkeypatch):
    monkeypatch.setattr(
        users,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=None,
                backend_available=False,
            )
        ),
    )
    session = FakeSession([])
    with pytest.raises(HTTPException) as raised:
        run(
            users.mark_notifications_read_through(
                payload=users.NotificationMarkReadThroughRequest(throughId=8),
                user=SimpleNamespace(id=7, telegram_id="700"),
                db=session,
            )
        )

    assert raised.value.status_code == 503
    assert session.statements == []


@pytest.mark.parametrize("through_id", [0, -1, 2_147_483_648])
def test_bulk_acknowledgement_rejects_unbounded_through_id(through_id):
    with pytest.raises(ValidationError):
        users.NotificationMarkReadThroughRequest(throughId=through_id)


def test_old_mark_all_route_remains_available():
    paths = {getattr(route, "path", "") for route in users.router.routes}
    assert "/api/notifications/mark-read" in paths
    assert "/api/notifications/{notification_id}/mark-read" in paths
    assert "/api/notifications/mark-read-through" in paths
