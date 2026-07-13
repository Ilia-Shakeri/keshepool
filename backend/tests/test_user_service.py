import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models import User, Wallet
from app.services.user_service import ensure_user_from_telegram_init, parse_telegram_user


class FakeScalarResult:
    def __init__(self, values):
        self.values = values

    def first(self):
        return self.values[0] if self.values else None

    def one(self):
        if len(self.values) != 1:
            raise AssertionError(f"Expected one row, got {len(self.values)}")
        return self.values[0]

    def all(self):
        return list(self.values)


class FakeResult:
    def __init__(self, values=(), scalar=None):
        self.values = list(values)
        self.scalar = scalar

    def scalars(self):
        return FakeScalarResult(self.values)

    def scalar_one_or_none(self):
        return self.scalar


class SharedBootstrapStore:
    def __init__(self, callers):
        self.users = {}
        self.wallets = {}
        self.next_user_id = 1
        self.next_wallet_id = 1
        self.lock = asyncio.Lock()
        self.initial_select_count = 0
        self.initial_select_ready = asyncio.Event()
        self.callers = callers


def _statement_values(statement):
    values = {}
    for column, bind_value in statement._values.items():
        key = getattr(column, "key", str(column))
        values[key] = getattr(bind_value, "value", bind_value)
    return values


def _where_telegram_id(statement):
    params = statement.compile().params
    return str(next(value for key, value in params.items() if "telegram_id" in key))


class FakeBootstrapSession:
    def __init__(self, shared):
        self.shared = shared
        self.initial_user_select_done = False
        self.commit_count = 0

    async def execute(self, statement):
        table_name = getattr(getattr(statement, "table", None), "name", None)
        if table_name == "users":
            values = _statement_values(statement)
            async with self.shared.lock:
                existing = self.shared.users.get(str(values["telegram_id"]))
                if existing is not None:
                    return FakeResult(scalar=None)
                user = User(**values)
                user.id = self.shared.next_user_id
                user.wallet = None
                self.shared.next_user_id += 1
                self.shared.users[user.telegram_id] = user
                return FakeResult(scalar=user.id)

        if table_name == "wallets":
            values = _statement_values(statement)
            async with self.shared.lock:
                existing = self.shared.wallets.get(values["user_id"])
                if existing is not None:
                    return FakeResult(scalar=None)
                wallet = Wallet(**values)
                wallet.id = self.shared.next_wallet_id
                self.shared.next_wallet_id += 1
                self.shared.wallets[wallet.user_id] = wallet
                user = next(
                    user for user in self.shared.users.values() if user.id == wallet.user_id
                )
                user.wallet = wallet
                return FakeResult(scalar=wallet.id)

        entity = statement.column_descriptions[0].get("entity")
        if entity is User:
            telegram_id = _where_telegram_id(statement)
            if not self.initial_user_select_done:
                self.initial_user_select_done = True
                snapshot = self.shared.users.get(telegram_id)
                self.shared.initial_select_count += 1
                if self.shared.initial_select_count == self.shared.callers:
                    self.shared.initial_select_ready.set()
                await self.shared.initial_select_ready.wait()
                return FakeResult(values=[snapshot] if snapshot else [])
            user = self.shared.users.get(telegram_id)
            return FakeResult(values=[user] if user else [])
        raise AssertionError(f"Unexpected statement: {statement}")

    async def commit(self):
        self.commit_count += 1

    async def rollback(self):
        raise AssertionError("Bootstrap should not roll back in this scenario")


def test_development_user_id_zero_is_valid():
    parsed = parse_telegram_user({"user": {"id": 0, "first_name": "Development"}})
    assert parsed["id"] == 0


def test_twelve_concurrent_bootstraps_create_one_user_and_wallet():
    caller_count = 12

    async def scenario():
        shared = SharedBootstrapStore(caller_count)
        sessions = [FakeBootstrapSession(shared) for _ in range(caller_count)]
        telegram_data = {
            "user": {
                "id": 9001,
                "username": "same-user",
                "first_name": "Same",
                "is_premium": False,
            }
        }
        users = await asyncio.gather(
            *(
                ensure_user_from_telegram_init(session, telegram_data)
                for session in sessions
            )
        )
        return shared, sessions, users

    shared, sessions, users = asyncio.run(scenario())
    assert len(shared.users) == 1
    assert len(shared.wallets) == 1
    assert {user.id for user in users} == {1}
    assert all(session.commit_count == 1 for session in sessions)


def test_existing_fresh_user_does_not_commit_on_read():
    async def scenario():
        shared = SharedBootstrapStore(callers=1)
        now = datetime.now(timezone.utc)
        user = User(
            telegram_id="9001",
            username="same-user",
            first_name="Same",
            last_name=None,
            language_code=None,
            photo_url=None,
            is_premium=False,
            role="user",
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        user.id = 1
        wallet = Wallet(user_id=1, balance=0)
        wallet.id = 1
        user.wallet = wallet
        shared.users[user.telegram_id] = user
        shared.wallets[user.id] = wallet
        session = FakeBootstrapSession(shared)
        shared.initial_select_ready.set()
        result = await ensure_user_from_telegram_init(
            session,
            {
                "user": {
                    "id": 9001,
                    "username": "same-user",
                    "first_name": "Same",
                    "is_premium": False,
                }
            },
        )
        return session, result

    session, result = asyncio.run(scenario())
    assert result.id == 1
    assert session.commit_count == 0
