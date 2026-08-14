import asyncio

from app.services import schema_compatibility_service as service


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class FakeSession:
    def __init__(self, revisions, tables):
        self.results = [FakeScalarResult(revisions), FakeScalarResult(tables)]

    async def execute(self, _statement):
        return self.results.pop(0)


def test_schema_check_requires_exact_head_and_all_core_tables(monkeypatch):
    monkeypatch.setattr(service, "expected_schema_heads", lambda: ("015",))
    compatible = asyncio.run(
        service.check_schema_compatibility(
            FakeSession(["015"], sorted(service._REQUIRED_TABLES))
        )
    )
    assert compatible.ready is True

    stale = asyncio.run(
        service.check_schema_compatibility(
            FakeSession(["014"], sorted(service._REQUIRED_TABLES - {"orders"}))
        )
    )
    assert stale.ready is False
    assert stale.missing_tables == ("orders",)


def test_release_has_one_real_migration_head():
    service.expected_schema_heads.cache_clear()
    heads = service.expected_schema_heads()
    assert len(heads) == 1
