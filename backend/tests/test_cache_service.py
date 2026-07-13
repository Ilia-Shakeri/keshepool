import asyncio

from redis.exceptions import RedisError

from app.services import cache_service


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.deleted = []
        self.rate_counts = {}

    async def get(self, key):
        return self.data.get(key)

    async def setex(self, key, ttl, value):
        self.data[key] = value
        return True

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return False
        self.data[key] = value
        return True

    async def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.data.pop(key, None)
        return len(keys)

    async def eval(self, script, number_of_keys, key, *args):
        if "incr" in script:
            self.rate_counts[key] = self.rate_counts.get(key, 0) + 1
            return self.rate_counts[key]
        token = args[0]
        if self.data.get(key) == token:
            self.data.pop(key, None)
            return 1
        return 0

    async def ping(self):
        return True


class OfflineRedis:
    def __getattr__(self, name):
        async def fail(*args, **kwargs):
            raise RedisError("offline")

        return fail


def run(coroutine):
    return asyncio.run(coroutine)


def test_json_cache_hit_miss_and_corrupt_entry_cleanup(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", fake)

    miss = run(cache_service.read_json("test:key"))
    assert miss.available is True
    assert miss.hit is False

    run(cache_service.write_json("test:key", {"ok": True}, 10))
    hit = run(cache_service.read_json("test:key"))
    assert hit.value == {"ok": True}

    fake.data["test:key"] = "{bad-json"
    corrupt = run(cache_service.read_json("test:key"))
    assert corrupt.hit is False
    assert "test:key" in fake.deleted


def test_catalog_falls_back_to_loader_when_redis_is_offline(monkeypatch):
    monkeypatch.setattr(cache_service, "redis_client", OfflineRedis())
    loader_calls = 0

    async def load():
        nonlocal loader_calls
        loader_calls += 1
        return [{"id": "db-product"}]

    result = run(cache_service.load_catalog_cached(load))
    assert result == [{"id": "db-product"}]
    assert loader_calls == 1
    assert run(cache_service.invalidate_catalog_cache()) is False


def test_concurrent_catalog_fill_uses_one_loader(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", fake)
    loader_calls = 0

    async def load():
        nonlocal loader_calls
        loader_calls += 1
        await asyncio.sleep(0.08)
        return [{"id": "shared"}]

    async def scenario():
        return await asyncio.gather(
            *(cache_service.load_catalog_cached(load) for _ in range(12))
        )

    results = run(scenario())
    assert loader_calls == 1
    assert all(result == [{"id": "shared"}] for result in results)


def test_rate_limit_is_atomic_and_namespaced(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", fake)

    decisions = [
        run(
            cache_service.check_rate_limit(
                "catalog",
                "user:42",
                limit=2,
                window_seconds=60,
            )
        )
        for _ in range(3)
    ]
    assert [decision.allowed for decision in decisions] == [True, True, False]
    only_key = next(iter(fake.rate_counts))
    assert only_key.startswith(f"{cache_service.settings.cache_namespace}:")
