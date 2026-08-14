import asyncio
import importlib.util
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.api import users
from app.models import User, Wallet
from app.services import user_service


OPAQUE_CODE = "0123456789abcdef0123456789abcdef"
OTHER_OPAQUE_CODE = "fedcba9876543210fedcba9876543210"


class FakeScalarResult:
    def __init__(self, values):
        self.values = list(values)

    def first(self):
        return self.values[0] if self.values else None

    def one(self):
        if len(self.values) != 1:
            raise AssertionError(f"Expected one row, got {len(self.values)}")
        return self.values[0]


class FakeResult:
    def __init__(self, values=(), scalar=None):
        self.values = list(values)
        self.scalar = scalar

    def scalars(self):
        return FakeScalarResult(self.values)

    def scalar_one_or_none(self):
        return self.scalar


class SequenceSession:
    def __init__(self, results):
        self.results = list(results)
        self.statements = []
        self.commit_count = 0
        self.rollback_count = 0

    async def execute(self, statement):
        self.statements.append(statement)
        if not self.results:
            raise AssertionError(f"Unexpected statement: {statement}")
        return self.results.pop(0)

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        self.rollback_count += 1


def _statement_values(statement):
    return {
        getattr(column, "key", str(column)): getattr(value, "value", value)
        for column, value in statement._values.items()
    }


def _new_user(telegram_id="200"):
    now = datetime.now(timezone.utc)
    user = User(
        telegram_id=telegram_id,
        username=None,
        first_name="Invitee",
        last_name=None,
        language_code=None,
        photo_url=None,
        is_premium=False,
        is_banned=False,
        role="user",
        referral_code=OTHER_OPAQUE_CODE,
        referrer_id=None,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    user.id = 20
    user.wallet = None
    return user


def _telegram_data(telegram_id="200"):
    return {
        "user": {
            "id": int(telegram_id),
            "first_name": "Invitee",
            "is_premium": False,
        }
    }


def test_signed_referral_uses_only_fixed_opaque_start_parameter():
    assert users.signed_referral_code({"start_param": f"ref_{OPAQUE_CODE}"}) == OPAQUE_CODE
    for invalid in (
        "ref_42",
        "ref_00042",
        "ref_-42",
        f"ref_{OPAQUE_CODE.upper()}",
        f"ref_{OPAQUE_CODE}0",
        f"bad_{OPAQUE_CODE}",
        OPAQUE_CODE,
        "",
    ):
        assert users.signed_referral_code({"start_param": invalid}) is None
    assert users.signed_referral_code({}) is None
    assert users.signed_referral_code({"start_param": 42}) is None


def test_referral_codes_are_random_fixed_and_unique():
    codes = {user_service.generate_referral_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(re.fullmatch(r"[0-9a-f]{32}", code) for code in codes)


def test_bootstrap_ignores_legacy_body_referrer(monkeypatch):
    captured = AsyncMock(return_value=SimpleNamespace(referral_code=OTHER_OPAQUE_CODE))
    monkeypatch.setattr(users, "ensure_user_from_telegram_init", captured)
    monkeypatch.setattr(users, "get_profile_payload", AsyncMock(return_value={"ok": True}))

    result = asyncio.run(
        users.bootstrap_user(
            users.BootstrapRequest(referrerTelegramId="999999"),
            telegram_data={"start_param": f"ref_{OPAQUE_CODE}"},
            db=SimpleNamespace(),
        )
    )

    assert result == {"ok": True}
    assert captured.await_args.kwargs["referral_code"] == OPAQUE_CODE
    assert "999999" not in repr(captured.await_args)


def test_new_user_attribution_resolves_opaque_code_and_is_in_insert():
    referrer = _new_user("100")
    referrer.id = 10
    referrer.referral_code = OPAQUE_CODE
    invitee = _new_user()
    session = SequenceSession(
        [
            FakeResult(),
            FakeResult(values=[referrer]),
            FakeResult(scalar=invitee.id),
            FakeResult(values=[invitee]),
            FakeResult(scalar=30),
        ]
    )

    result = asyncio.run(
        user_service.ensure_user_from_telegram_init(
            session,
            _telegram_data(),
            referral_code=OPAQUE_CODE,
        )
    )

    user_insert = next(
        statement
        for statement in session.statements
        if getattr(getattr(statement, "table", None), "name", None) == "users"
    )
    values = _statement_values(user_insert)
    assert values["referrer_id"] == referrer.id
    assert re.fullmatch(r"[0-9a-f]{32}", values["referral_code"])
    assert result.id == invitee.id
    assert session.commit_count == 1


def test_existing_user_cannot_be_re_attributed():
    existing = _new_user()
    existing.referrer_id = 10
    existing.wallet = Wallet(id=1, user_id=existing.id, balance=0)
    session = SequenceSession([FakeResult(values=[existing])])

    result = asyncio.run(
        user_service.ensure_user_from_telegram_init(
            session,
            _telegram_data(),
            referral_code=OPAQUE_CODE,
        )
    )

    assert result.referrer_id == 10
    assert len(session.statements) == 1
    assert session.commit_count == 0


def test_referral_code_collision_retries_without_losing_attribution(monkeypatch):
    invitee = _new_user()
    generated = iter([OPAQUE_CODE, OTHER_OPAQUE_CODE])
    monkeypatch.setattr(user_service, "generate_referral_code", lambda: next(generated))
    session = SequenceSession(
        [
            FakeResult(),
            FakeResult(scalar=None),
            FakeResult(),
            FakeResult(scalar=invitee.id),
            FakeResult(values=[invitee]),
            FakeResult(scalar=30),
        ]
    )

    asyncio.run(user_service.ensure_user_from_telegram_init(session, _telegram_data()))

    inserts = [
        statement
        for statement in session.statements
        if getattr(getattr(statement, "table", None), "name", None) == "users"
    ]
    assert [_statement_values(statement)["referral_code"] for statement in inserts] == [
        OPAQUE_CODE,
        OTHER_OPAQUE_CODE,
    ]
    assert session.rollback_count == 0


def test_model_and_migration_enforce_opaque_unique_immutable_attribution():
    constraints = {constraint.name for constraint in User.__table__.constraints}
    assert {
        "uq_users_referral_code",
        "ck_users_referral_code_format",
        "ck_users_no_self_referral",
    }.issubset(constraints)
    assert User.__table__.c.referral_code.nullable is False
    assert "gen_random_uuid" in str(User.__table__.c.referral_code.server_default.arg)

    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "013_opaque_referral_codes.py"
    )
    spec = importlib.util.spec_from_file_location("migration_013", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    source = migration_path.read_text(encoding="utf-8")

    assert migration.revision == "013"
    assert migration.down_revision == "012"
    assert "gen_random_uuid" in source
    assert "trg_users_protect_referrer_id" in source
    assert "OLD.referrer_id IS NOT NULL" in source
