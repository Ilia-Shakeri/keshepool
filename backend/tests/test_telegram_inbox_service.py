import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.models import TelegramUpdateInbox
from app.services import telegram_inbox_service as service
from app.workers import telegram_inbox as worker


class FakeResult:
    def __init__(self, *, rowcount=0, rows=()):
        self.rowcount = rowcount
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, *results):
        self.results = list(results)
        self.statements = []
        self.commits = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0)

    async def commit(self):
        self.commits += 1


class FakeSessionContext:
    async def __aenter__(self):
        return SimpleNamespace()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def run(awaitable):
    return asyncio.run(awaitable)


def _compiled_params(statement):
    return statement.compile(dialect=postgresql.dialect()).params


def test_claim_adds_distinct_fences_and_has_database_attempt_cap():
    first = TelegramUpdateInbox(
        id=1,
        bot_type="main",
        update_id=101,
        payload={"update_id": 101},
        status="pending",
        attempts=0,
    )
    second = TelegramUpdateInbox(
        id=2,
        bot_type="admin",
        update_id=102,
        payload={"update_id": 102},
        status="retry",
        attempts=1,
    )
    session = FakeSession(
        FakeResult(),
        FakeResult(rows=(first, second)),
    )

    claimed = run(
        service.claim_updates(
            session,
            limit=2,
            stale_after_seconds=30,
            max_attempts=3,
        )
    )

    assert claimed == [first, second]
    assert (first.attempts, second.attempts) == (1, 2)
    assert first.status == second.status == "processing"
    assert len(first.claim_token) >= 32
    assert len(second.claim_token) >= 32
    assert first.claim_token != second.claim_token
    select_sql = str(session.statements[1].compile(dialect=postgresql.dialect()))
    assert "telegram_update_inbox.attempts <" in select_sql
    assert "FOR UPDATE SKIP LOCKED" in select_sql
    retire_params = _compiled_params(session.statements[0])
    assert service.MAX_ATTEMPTS_ERROR in retire_params.values()
    assert {} in retire_params.values()
    assert session.commits == 1


def test_done_transition_needs_fence_and_erases_payload():
    accepted = FakeSession(FakeResult(rowcount=1))
    rejected = FakeSession(FakeResult(rowcount=0))

    assert run(service.mark_update_done(accepted, 7, claim_token="a" * 43)) is True
    assert run(service.mark_update_done(rejected, 7, claim_token="stale" * 8)) is False

    params = _compiled_params(accepted.statements[0])
    assert "a" * 43 in params.values()
    assert "processing" in params.values()
    assert "done" in params.values()
    assert {} in params.values()


def test_failed_transition_erases_payload_only_when_terminal():
    terminal = FakeSession(FakeResult(rowcount=1))
    retry = FakeSession(FakeResult(rowcount=0), FakeResult(rowcount=1))

    assert run(
        service.mark_update_failed(
            terminal,
            9,
            claim_token="b" * 43,
            max_attempts=2,
            retry_delay_seconds=10,
            error_class="ValueError",
        )
    ) is True
    assert {} in _compiled_params(terminal.statements[0]).values()

    assert run(
        service.mark_update_failed(
            retry,
            9,
            claim_token="c" * 43,
            max_attempts=2,
            retry_delay_seconds=10,
            error_class="ValueError",
        )
    ) is True
    assert {} not in _compiled_params(retry.statements[1]).values()


def test_failed_transition_rejects_nonpositive_retry_delay():
    with pytest.raises(ValueError, match="retry_delay_seconds"):
        run(
            service.mark_update_failed(
                FakeSession(),
                9,
                claim_token="c" * 43,
                max_attempts=2,
                retry_delay_seconds=0,
                error_class="ValueError",
            )
        )


def test_heartbeat_renews_until_database_rejects_fence(monkeypatch):
    renew = AsyncMock(side_effect=(True, False))
    monkeypatch.setattr(worker, "renew_update_claim", renew)
    monkeypatch.setattr(worker, "AsyncSessionLocal", lambda: FakeSessionContext())

    run(
        worker._heartbeat_claim(
            11,
            "d" * 43,
            asyncio.Event(),
            interval_seconds=0.001,
        )
    )

    assert renew.await_count == 2
    assert renew.await_args_list[0].kwargs == {"claim_token": "d" * 43}


def test_revision_011_matches_model_and_follows_010():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "011_telegram_inbox_claim_fence.py"
    )
    spec = importlib.util.spec_from_file_location("migration_011", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    assert migration.revision == "011"
    assert migration.down_revision == "010"
    assert "claim_token" in TelegramUpdateInbox.__table__.c
    constraints = {
        constraint.name for constraint in TelegramUpdateInbox.__table__.constraints
    }
    assert "ck_telegram_update_claim_token_length" in constraints
    migration_source = migration_path.read_text(encoding="utf-8")
    assert "WHERE status IN ('done', 'failed')" in migration_source
