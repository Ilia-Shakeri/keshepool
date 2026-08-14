import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models import AdminActionNonce, AdminApprovalRequest
from app.services import admin_authorization_service as service
from app.services import admin_audit_service


class FakeSession:
    def __init__(self, *, scalar_result=None, rowcount=1):
        self.added = []
        self.scalar_result = scalar_result
        self.rowcount = rowcount

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        for index, value in enumerate(self.added, start=1):
            if getattr(value, "id", None) is None:
                value.id = index

    async def execute(self, statement):
        return SimpleNamespace(rowcount=self.rowcount)

    async def scalar(self, statement):
        return self.scalar_result


def run(awaitable):
    return asyncio.run(awaitable)


def test_nonce_is_stored_as_hash_and_bound_to_full_action_context():
    session = FakeSession()
    raw = run(
        service.issue_action_nonce(
            session,
            actor_telegram_id="42",
            chat_id="-1001",
            action="wallet.adjust",
            target_type="user",
            target_id="88",
        )
    )
    row = session.added[0]
    assert isinstance(row, AdminActionNonce)
    assert row.nonce_hash == service.payload_digest(raw.encode("ascii"))
    assert raw not in row.nonce_hash
    assert (row.actor_telegram_id, row.chat_id, row.action, row.target_id) == (
        "42",
        "-1001",
        "wallet.adjust",
        "88",
    )


def test_nonce_consume_rejects_replay_or_context_mismatch():
    with pytest.raises(service.AdminAuthorizationError, match="nonce rejected"):
        run(
            service.consume_action_nonce(
                FakeSession(rowcount=0),
                nonce="old-or-wrong",
                actor_telegram_id="42",
                chat_id="-1001",
                action="wallet.adjust",
                target_type="user",
                target_id="88",
            )
        )


def test_approval_request_is_payload_bound_and_needs_two_admins():
    session = FakeSession()
    with patch.object(service, "require_action_role", AsyncMock(return_value=frozenset({"finance"}))):
        request = run(
            service.create_approval_request(
                session,
                actor_telegram_id="42",
                action="wallet.adjust",
                target_type="user",
                target_id="88",
                payload=b'{"amount":"1000"}',
            )
        )
    assert isinstance(request, AdminApprovalRequest)
    assert request.required_approvals == 2
    assert request.payload_hash == service.payload_digest(b'{"amount":"1000"}')


def test_requester_cannot_supply_second_approval():
    request = SimpleNamespace(
        id=9,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        requested_by_telegram_id="42",
        payload_hash=service.payload_digest(b"same"),
        action="wallet.adjust",
    )
    with pytest.raises(service.AdminAuthorizationError, match="Second administrator"):
        run(
            service.approve_request(
                FakeSession(scalar_result=request),
                approval_request_id=9,
                actor_telegram_id="42",
                payload=b"same",
            )
        )


def test_second_admin_cannot_approve_changed_payload():
    request = SimpleNamespace(
        id=9,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        requested_by_telegram_id="42",
        payload_hash=service.payload_digest(b"old"),
        action="wallet.adjust",
    )
    with pytest.raises(service.AdminAuthorizationError, match="payload changed"):
        run(
            service.approve_request(
                FakeSession(scalar_result=request),
                approval_request_id=9,
                actor_telegram_id="43",
                payload=b"new",
            )
        )


@pytest.mark.parametrize("value", ["", "0", "01", "-1", "not-a-number", "1" * 21])
def test_admin_role_target_requires_bounded_positive_telegram_id(value):
    with pytest.raises(service.AdminAuthorizationError, match="Telegram user ID"):
        service._telegram_id(value)


def test_admin_role_target_accepts_valid_telegram_id():
    assert service._telegram_id("123456789") == "123456789"


def test_audit_scrub_redacts_secret_shapes_even_under_plain_key():
    assert admin_audit_service._safe_value(
        {"value": "123456789:abcdefghijklmnopqrstuvwxyzABCDEFGH1234"}
    ) == {"value": "[redacted]"}
    assert admin_audit_service._safe_value(
        {"value": "auth_date=1&hash=hidden"}
    ) == {"value": "[redacted]"}
    assert admin_audit_service._safe_value(
        {
            "initData": "raw-user-data",
            "api_key": "key-value",
            "callback_signature": "signed-value",
            "cashout_details": "private-financial-text",
            "safe_count": 3,
        }
    ) == {
        "initData": "[redacted]",
        "api_key": "[redacted]",
        "callback_signature": "[redacted]",
        "cashout_details": "[redacted]",
        "safe_count": 3,
    }
    assert admin_audit_service._safe_value(
        {"value": "Authorization: Bearer sample-value"}
    ) == {"value": "[redacted]"}


def test_audit_context_is_scoped_and_reset():
    assert admin_audit_service._AUDIT_CONTEXT.get() == {}
    with admin_audit_service.admin_audit_context(update_id=7, chat_id=-1001):
        assert admin_audit_service._AUDIT_CONTEXT.get() == {
            "update_id": 7,
            "chat_id": "-1001",
        }
    assert admin_audit_service._AUDIT_CONTEXT.get() == {}
