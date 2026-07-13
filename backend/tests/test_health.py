import asyncio
import json

from app import main


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, statement):
        return 1


def test_liveness_and_readiness_routes_are_distinct():
    paths = {route.path for route in main.app.routes}
    assert "/health/live" in paths
    assert "/health/ready" in paths
    assert "/health" in paths


def test_readiness_documents_database_fallback_when_redis_is_down(monkeypatch):
    monkeypatch.setattr(main, "AsyncSessionLocal", FakeSession)

    async def redis_down():
        return False, "ConnectionError"

    monkeypatch.setattr(main, "redis_health", redis_down)
    response = asyncio.run(main.readiness_check())
    payload = json.loads(response.body)
    assert response.status_code == 200
    assert payload["status"] == "degraded"
    assert payload["ready"] is True
    assert payload["checks"]["redis"]["fallback"] == "database"


def test_public_support_config_returns_only_safe_telegram_links(monkeypatch):
    monkeypatch.setattr(main.settings, "SUPPORT_TELEGRAM_USERNAME", "@safe_support")
    payload = asyncio.run(main.get_public_config())
    assert payload["supportUsername"] == "safe_support"
    assert payload["supportUrl"] == "https://t.me/safe_support"

    monkeypatch.setattr(main.settings, "SUPPORT_TELEGRAM_USERNAME", "bad/name")
    payload = asyncio.run(main.get_public_config())
    assert payload["supportUsername"] is None
    assert payload["supportUrl"] is None
