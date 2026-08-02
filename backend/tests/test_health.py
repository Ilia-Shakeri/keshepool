import asyncio
import json
from pathlib import Path

from app import main
from starlette.requests import Request
from starlette.responses import Response


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def execute(self, statement):
        return 1


def test_liveness_and_readiness_routes_are_distinct():
    paths = {
        path
        for route in main.app.routes
        if (path := getattr(route, "path", None)) is not None
    }
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


def test_browser_security_headers_keep_telegram_embedding(monkeypatch):
    monkeypatch.setattr(main.settings, "CSP_REPORT_ONLY", True)
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    async def call_next(_request):
        return Response("ok")

    response = asyncio.run(main.add_correlation_id(request, call_next))
    policy = response.headers["Content-Security-Policy-Report-Only"]
    assert "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org" in policy
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Frame-Options" not in response.headers


def test_edge_headers_and_direct_sensitive_routes_are_declared():
    caddyfile = (
        Path(__file__).resolve().parents[2] / "ops" / "Caddyfile.example"
    ).read_text(encoding="utf-8")
    assert "Content-Security-Policy-Report-Only" in caddyfile
    assert "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org" in caddyfile
    assert "X-Frame-Options" not in caddyfile
    assert "handle /webhook/*" in caddyfile
    assert "handle /api/pay/tetra98/callback" in caddyfile
    assert "handle /static/*" in caddyfile
