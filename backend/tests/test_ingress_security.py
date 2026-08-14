import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.responses import Response

from app import main
from app.core.config import Settings
from app.services import ingress_security
from app.services.cache_service import RateLimitDecision
from app.services.ingress_security import (
    InFlightDecision,
    IngressDecision,
    IngressLease,
)


def make_request(
    path: str,
    *,
    method: str = "GET",
    client: tuple[str, int] | None = ("203.0.113.8", 43120),
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "scheme": "https",
            "server": ("keshepool.example.com", 443),
            "client": client,
            "headers": headers or [],
        }
    )


def settings_values(**overrides):
    values = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql+asyncpg://user:password@db/test",
        "BOT_TOKEN": "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "ADMIN_BOT_TOKEN": "123457:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "WEBHOOK_URL": "https://example.test",
        "MAIN_TELEGRAM_WEBHOOK_SECRET": "test-main-webhook-secret",
        "ADMIN_TELEGRAM_WEBHOOK_SECRET": "test-admin-webhook-secret",
        "WEB_APP_URL": "https://example.test",
        "ADMIN_TELEGRAM_IDS": "123456",
        "USDT_TO_IRR_RATE": 85000,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/webhook/main", "webhook-main"),
        ("POST", "/webhook/admin/", "webhook-admin"),
        ("GET", "/webhook/not-a-bot", "webhook-unknown"),
        ("POST", "/api/pay/tetra98/callback", "payment-callback"),
        ("POST", "/api/pay/crypto/callback", "payment-callback"),
        ("GET", "/api/admin/stats", "admin-api"),
        ("POST", "/api/me/bootstrap", "auth-bootstrap"),
        ("POST", "/api/checkout", "checkout"),
        ("POST", "/api/pay/crypto/initiate", "payment-write"),
        ("POST", "/api/cashout", "cashout"),
        (
            "POST",
            "/api/orders/order-1/reveal-credential",
            "credential-reveal",
        ),
        ("HEAD", "/api/products", "api-read"),
        ("POST", "/api/notifications/mark-read", None),
        ("GET", "/health/ready", None),
    ],
)
def test_ingress_policy_is_path_and_method_specific(method, path, expected):
    policy = ingress_security.ingress_policy(method, path)
    assert (policy.name if policy else None) == expected


def test_every_sensitive_ingress_policy_fails_closed():
    policies = (
        ingress_security.WEBHOOK_MAIN_POLICY,
        ingress_security.WEBHOOK_ADMIN_POLICY,
        ingress_security.WEBHOOK_UNKNOWN_POLICY,
        ingress_security.PAYMENT_CALLBACK_POLICY,
        ingress_security.ADMIN_API_POLICY,
        ingress_security.AUTH_BOOTSTRAP_POLICY,
        ingress_security.CHECKOUT_POLICY,
        ingress_security.PAYMENT_WRITE_POLICY,
        ingress_security.CASHOUT_POLICY,
        ingress_security.CREDENTIAL_REVEAL_POLICY,
    )
    assert all(policy.fail_closed for policy in policies)
    assert ingress_security.ORDINARY_API_READ_POLICY.fail_closed is False


def test_effective_client_identity_ignores_spoofed_ip_headers():
    request = make_request(
        "/api/products",
        headers=[
            (b"forwarded", b"for=198.51.100.1"),
            (b"x-forwarded-for", b"198.51.100.2"),
            (b"x-real-ip", b"198.51.100.3"),
            (b"cf-connecting-ip", b"198.51.100.4"),
        ],
    )
    assert ingress_security.effective_client_identity(request) == "ip:203.0.113.8"


def test_effective_client_identity_accepts_one_ip_from_trusted_proxy(monkeypatch):
    monkeypatch.setattr(
        ingress_security.settings,
        "TRUSTED_PROXY_IPS",
        "172.30.0.0/24,127.0.0.1",
    )
    request = make_request(
        "/api/products",
        client=("172.30.0.8", 43120),
        headers=[(b"x-forwarded-for", b"2001:db8::7")],
    )
    assert ingress_security.effective_client_identity(request) == "ip:2001:db8::7"


def test_effective_client_identity_rejects_forwarding_chains(monkeypatch):
    monkeypatch.setattr(
        ingress_security.settings,
        "TRUSTED_PROXY_IPS",
        "172.30.0.0/24",
    )
    request = make_request(
        "/api/products",
        client=("172.30.0.8", 43120),
        headers=[(b"x-forwarded-for", b"198.51.100.2, 198.51.100.3")],
    )
    assert ingress_security.effective_client_identity(request) == "ip:172.30.0.8"


def test_effective_client_identity_rejects_duplicate_forwarded_headers(monkeypatch):
    monkeypatch.setattr(
        ingress_security.settings,
        "TRUSTED_PROXY_IPS",
        "172.30.0.0/24",
    )
    request = make_request(
        "/api/products",
        client=("172.30.0.8", 43120),
        headers=[
            (b"x-forwarded-for", b"198.51.100.2"),
            (b"x-forwarded-for", b"198.51.100.3"),
        ],
    )
    assert ingress_security.effective_client_identity(request) == "ip:172.30.0.8"


def test_callback_source_allowlist_uses_hardened_effective_ip(monkeypatch):
    monkeypatch.setattr(
        ingress_security.settings,
        "TRUSTED_PROXY_IPS",
        "172.30.0.0/24",
    )
    monkeypatch.setattr(
        ingress_security.settings,
        "TETRA98_CALLBACK_ALLOWED_CIDRS",
        "198.51.100.0/24,2001:db8::/32",
    )
    request = make_request(
        "/api/pay/tetra98/callback",
        method="POST",
        client=("172.30.0.8", 43120),
        headers=[(b"x-forwarded-for", b"198.51.100.25")],
    )
    decision = ingress_security.callback_source_decision(request)
    assert decision.configured is True
    assert decision.config_valid is True
    assert decision.allowed is True


def test_callback_source_allowlist_is_disabled_when_blank(monkeypatch):
    monkeypatch.setattr(
        ingress_security.settings,
        "CRYPTO_CALLBACK_ALLOWED_CIDRS",
        "",
    )
    decision = ingress_security.callback_source_decision(
        make_request("/api/pay/crypto/callback", method="POST")
    )
    assert decision.configured is False
    assert decision.allowed is True


def test_callback_source_denial_happens_before_redis(monkeypatch):
    monkeypatch.setattr(
        ingress_security.settings,
        "TETRA98_CALLBACK_ALLOWED_CIDRS",
        "198.51.100.0/24",
    )
    rate_limit = AsyncMock()
    acquire = AsyncMock()
    monkeypatch.setattr(ingress_security, "check_rate_limit", rate_limit)
    monkeypatch.setattr(ingress_security, "acquire_ingress_slot", acquire)

    decision = asyncio.run(
        ingress_security.check_ingress_request(
            make_request("/api/pay/tetra98/callback", method="POST")
        )
    )
    assert decision.blocked_status == 403
    assert decision.block_reason == "callback_source_denied"
    rate_limit.assert_not_awaited()
    acquire.assert_not_awaited()


def test_malformed_callback_source_config_fails_closed(monkeypatch):
    monkeypatch.setattr(
        ingress_security.settings,
        "CRYPTO_CALLBACK_ALLOWED_CIDRS",
        "198.51.100.9/24",
    )
    rate_limit = AsyncMock()
    monkeypatch.setattr(ingress_security, "check_rate_limit", rate_limit)

    decision = asyncio.run(
        ingress_security.check_ingress_request(
            make_request("/api/pay/crypto/callback", method="POST")
        )
    )
    assert decision.blocked_status == 503
    assert decision.block_reason == "callback_source_config_invalid"
    rate_limit.assert_not_awaited()


def test_settings_reject_malformed_callback_cidrs():
    with pytest.raises(ValidationError, match="valid exact IPv4 or IPv6 CIDRs"):
        Settings(
            **settings_values(
                TETRA98_CALLBACK_ALLOWED_CIDRS="198.51.100.9/24",
            )
        )
    with pytest.raises(ValidationError, match="explicit CIDRs"):
        Settings(
            **settings_values(
                CRYPTO_CALLBACK_ALLOWED_CIDRS="198.51.100.0/24,",
            )
        )


def test_settings_reject_malformed_trusted_proxy_networks():
    with pytest.raises(ValidationError, match="valid exact IPv4 or IPv6"):
        Settings(
            **settings_values(
                TRUSTED_PROXY_IPS="172.30.0.8/24",
            )
        )
    with pytest.raises(ValidationError, match="explicit proxy addresses"):
        Settings(
            **settings_values(
                TRUSTED_PROXY_IPS="127.0.0.1,",
            )
        )


def test_inflight_lease_uses_atomic_expiry_cleanup_and_fenced_release(monkeypatch):
    evaluate = AsyncMock(side_effect=[[1, 1], 1])
    monkeypatch.setattr(ingress_security.redis_client, "eval", evaluate)
    monkeypatch.setattr(
        ingress_security.settings,
        "INGRESS_SENSITIVE_MAX_IN_FLIGHT",
        7,
    )
    monkeypatch.setattr(
        ingress_security.settings,
        "INGRESS_IN_FLIGHT_TTL_SECONDS",
        45,
    )

    decision = asyncio.run(
        ingress_security.acquire_ingress_slot(
            ingress_security.PAYMENT_CALLBACK_POLICY
        )
    )
    assert decision.allowed is True
    assert decision.backend_available is True
    assert decision.lease is not None

    acquire_args = evaluate.await_args_list[0].args
    acquire_script = acquire_args[0].lower()
    assert "redis.call('time')" in acquire_script
    assert "zremrangebyscore" in acquire_script
    assert "zadd" in acquire_script
    assert "pexpire" in acquire_script
    assert acquire_args[-2:] == (7, 45)

    asyncio.run(ingress_security.release_ingress_slot(decision.lease))
    release_args = evaluate.await_args_list[1].args
    release_script = release_args[0].lower()
    assert "zrem" in release_script
    assert "zcard" in release_script
    assert release_args[-1] == decision.lease.token


def test_inflight_guard_failure_is_fail_closed(monkeypatch):
    monkeypatch.setattr(
        ingress_security.redis_client,
        "eval",
        AsyncMock(side_effect=RedisError("offline")),
    )
    decision = asyncio.run(
        ingress_security.acquire_ingress_slot(
            ingress_security.PAYMENT_CALLBACK_POLICY
        )
    )
    assert decision.allowed is False
    assert decision.backend_available is False


def test_sensitive_ingress_returns_shared_lease(monkeypatch):
    monkeypatch.setattr(
        ingress_security,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=1,
                backend_available=True,
            )
        ),
    )
    lease = IngressLease("test-key", "test-token")
    monkeypatch.setattr(
        ingress_security,
        "acquire_ingress_slot",
        AsyncMock(
            return_value=InFlightDecision(
                allowed=True,
                backend_available=True,
                lease=lease,
            )
        ),
    )
    decision = asyncio.run(
        ingress_security.check_ingress_request(
            make_request("/api/checkout", method="POST")
        )
    )
    assert decision.blocked_status is None
    assert decision.lease == lease


def test_sensitive_ingress_rejects_when_shared_cap_is_full(monkeypatch):
    monkeypatch.setattr(
        ingress_security,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=1,
                backend_available=True,
            )
        ),
    )
    monkeypatch.setattr(
        ingress_security,
        "acquire_ingress_slot",
        AsyncMock(
            return_value=InFlightDecision(
                allowed=False,
                backend_available=True,
            )
        ),
    )
    decision = asyncio.run(
        ingress_security.check_ingress_request(
            make_request("/api/cashout", method="POST")
        )
    )
    assert decision.blocked_status == 429
    assert decision.block_reason == "concurrency_limited"


def test_sensitive_ingress_fails_closed_when_limiter_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        ingress_security,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=None,
                backend_available=False,
            )
        ),
    )
    decision = asyncio.run(
        ingress_security.check_ingress_request(
            make_request("/webhook/main", method="POST")
        )
    )
    assert decision.blocked_status == 503


def test_ordinary_read_stays_available_when_limiter_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        ingress_security,
        "check_rate_limit",
        AsyncMock(
            return_value=RateLimitDecision(
                allowed=True,
                count=None,
                backend_available=False,
            )
        ),
    )
    decision = asyncio.run(
        ingress_security.check_ingress_request(make_request("/api/products"))
    )
    assert decision.policy.name == "api-read"
    assert decision.blocked_status is None


def test_ingress_uses_canonical_peer_identity_and_policy_budget(monkeypatch):
    rate_limit = AsyncMock(
        return_value=RateLimitDecision(
            allowed=False,
            count=301,
            backend_available=True,
        )
    )
    monkeypatch.setattr(ingress_security, "check_rate_limit", rate_limit)
    decision = asyncio.run(
        ingress_security.check_ingress_request(
            make_request(
                "/api/me/bootstrap",
                method="POST",
                headers=[(b"x-forwarded-for", b"192.0.2.99")],
            )
        )
    )
    assert decision.blocked_status == 429
    rate_limit.assert_awaited_once_with(
        "ingress:auth-bootstrap",
        "ip:203.0.113.8",
        limit=300,
        window_seconds=60,
    )


def test_rate_limited_response_skips_route_and_keeps_security_headers(monkeypatch):
    monkeypatch.setattr(
        main,
        "check_ingress_request",
        AsyncMock(
            return_value=IngressDecision(
                ingress_security.WEBHOOK_MAIN_POLICY,
                allowed=False,
                backend_available=True,
            )
        ),
    )
    downstream = AsyncMock(return_value=Response("must not run"))
    response = asyncio.run(
        main.add_correlation_id(
            make_request("/webhook/main", method="POST"),
            downstream,
        )
    )
    payload = json.loads(response.body)
    assert response.status_code == 429
    assert payload == {"detail": "Too many requests."}
    assert response.headers["Retry-After"] == "60"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-ID"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    downstream.assert_not_awaited()


def test_middleware_releases_shared_lease_after_route(monkeypatch):
    lease = IngressLease("test-key", "test-token")
    monkeypatch.setattr(
        main,
        "check_ingress_request",
        AsyncMock(
            return_value=IngressDecision(
                ingress_security.CHECKOUT_POLICY,
                allowed=True,
                backend_available=True,
                lease=lease,
            )
        ),
    )
    release = AsyncMock()
    monkeypatch.setattr(main, "release_ingress_slot", release)
    response = asyncio.run(
        main.add_correlation_id(
            make_request("/api/checkout", method="POST"),
            AsyncMock(return_value=Response("ok")),
        )
    )
    assert response.status_code == 200
    release.assert_awaited_once_with(lease)


def test_middleware_releases_shared_lease_when_route_raises(monkeypatch):
    lease = IngressLease("test-key", "test-token")
    monkeypatch.setattr(
        main,
        "check_ingress_request",
        AsyncMock(
            return_value=IngressDecision(
                ingress_security.CHECKOUT_POLICY,
                allowed=True,
                backend_available=True,
                lease=lease,
            )
        ),
    )
    release = AsyncMock()
    monkeypatch.setattr(main, "release_ingress_slot", release)
    downstream = AsyncMock(side_effect=RuntimeError("route failed"))
    with pytest.raises(RuntimeError, match="route failed"):
        asyncio.run(
            main.add_correlation_id(
                make_request("/api/checkout", method="POST"),
                downstream,
            )
        )
    release.assert_awaited_once_with(lease)


def test_caddy_rejects_client_ip_headers_and_bounds_callback_bodies():
    caddyfile = (
        Path(__file__).resolve().parents[2] / "ops" / "Caddyfile.example"
    ).read_text(encoding="utf-8")
    for header_name in (
        "Forwarded",
        "X-Forwarded-Port",
        "X-Real-IP",
        "Client-IP",
        "True-Client-IP",
        "CF-Connecting-IP",
    ):
        assert f"header_up -{header_name}" in caddyfile
    assert "trusted_proxies" not in caddyfile
    assert "rebuilt by reverse_proxy" in caddyfile
    assert caddyfile.count("request>headers>X-Tetra98-Signature delete") == 2
    assert caddyfile.count("request>headers>X-Crypto-Signature delete") == 2
    assert caddyfile.count("max_size 1MB") == 3
    assert "handle /health/live" in caddyfile


def test_compose_requires_explicit_trusted_proxy_peers():
    compose = (
        Path(__file__).resolve().parents[2] / "docker-compose.yml"
    ).read_text(encoding="utf-8")
    assert compose.count("TRUSTED_PROXY_IPS=${TRUSTED_PROXY_IPS:?") == 2
    assert "TRUSTED_PROXY_IPS=${TRUSTED_PROXY_IPS:-" not in compose
    assert (
        "INGRESS_SENSITIVE_MAX_IN_FLIGHT=${INGRESS_SENSITIVE_MAX_IN_FLIGHT:-64}"
        in compose
    )
    assert (
        "INGRESS_IN_FLIGHT_TTL_SECONDS=${INGRESS_IN_FLIGHT_TTL_SECONDS:-120}"
        in compose
    )
    assert "TETRA98_CALLBACK_ALLOWED_CIDRS=${TETRA98_CALLBACK_ALLOWED_CIDRS:-}" in compose
    assert "CRYPTO_CALLBACK_ALLOWED_CIDRS=${CRYPTO_CALLBACK_ALLOWED_CIDRS:-}" in compose

    env_example = (
        Path(__file__).resolve().parents[2] / ".env.example"
    ).read_text(encoding="utf-8")
    assert "TETRA98_CALLBACK_ALLOWED_CIDRS=\n" in env_example
    assert "CRYPTO_CALLBACK_ALLOWED_CIDRS=\n" in env_example
