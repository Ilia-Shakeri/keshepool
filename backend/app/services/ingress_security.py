import hashlib
import logging
import re
import secrets
from dataclasses import dataclass
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from typing import Literal

from fastapi import Request

from app.core.config import settings
from app.core.redis import redis_client
from app.services.cache_service import (
    RateLimitDecision,
    check_rate_limit,
    namespaced_key,
)


logger = logging.getLogger(__name__)

_REVEAL_CREDENTIAL_PATH = re.compile(
    r"^/api/orders/[^/]+/reveal-credential$"
)


@dataclass(frozen=True)
class IngressPolicy:
    name: str
    limit: int
    window_seconds: int
    fail_closed: bool


@dataclass(frozen=True)
class IngressLease:
    key: str
    token: str


IngressBlockReason = Literal[
    "rate_limited",
    "limiter_unavailable",
    "concurrency_limited",
    "concurrency_guard_unavailable",
    "callback_source_denied",
    "callback_source_config_invalid",
]


@dataclass(frozen=True)
class IngressDecision:
    policy: IngressPolicy | None
    allowed: bool
    backend_available: bool
    lease: IngressLease | None = None
    block_reason: IngressBlockReason | None = None

    @property
    def blocked_status(self) -> int | None:
        if self.policy is None:
            return None
        if self.block_reason == "callback_source_denied":
            return 403
        if not self.backend_available:
            return 503 if self.policy.fail_closed else None
        return None if self.allowed else 429


@dataclass(frozen=True)
class InFlightDecision:
    allowed: bool
    backend_available: bool
    lease: IngressLease | None = None


@dataclass(frozen=True)
class CallbackSourceDecision:
    configured: bool
    allowed: bool
    config_valid: bool


WEBHOOK_MAIN_POLICY = IngressPolicy("webhook-main", 600, 60, True)
WEBHOOK_ADMIN_POLICY = IngressPolicy("webhook-admin", 300, 60, True)
WEBHOOK_UNKNOWN_POLICY = IngressPolicy("webhook-unknown", 60, 60, True)
PAYMENT_CALLBACK_POLICY = IngressPolicy("payment-callback", 300, 60, True)
ADMIN_API_POLICY = IngressPolicy("admin-api", 120, 60, True)
AUTH_BOOTSTRAP_POLICY = IngressPolicy("auth-bootstrap", 300, 60, True)
CHECKOUT_POLICY = IngressPolicy("checkout", 120, 60, True)
PAYMENT_WRITE_POLICY = IngressPolicy("payment-write", 120, 60, True)
CASHOUT_POLICY = IngressPolicy("cashout", 60, 60, True)
CREDENTIAL_REVEAL_POLICY = IngressPolicy("credential-reveal", 60, 60, True)
ORDINARY_API_READ_POLICY = IngressPolicy("api-read", 600, 60, False)


def ingress_policy(method: str, raw_path: str) -> IngressPolicy | None:
    method = method.upper()
    path = raw_path if raw_path == "/" else raw_path.rstrip("/")

    if path == "/webhook/main":
        return WEBHOOK_MAIN_POLICY
    if path == "/webhook/admin":
        return WEBHOOK_ADMIN_POLICY
    if path == "/webhook" or path.startswith("/webhook/"):
        return WEBHOOK_UNKNOWN_POLICY

    if path in {
        "/api/pay/tetra98/callback",
        "/api/pay/crypto/callback",
    }:
        return PAYMENT_CALLBACK_POLICY

    if path == "/api/admin" or path.startswith("/api/admin/"):
        return ADMIN_API_POLICY

    if method == "POST":
        if path == "/api/me/bootstrap":
            return AUTH_BOOTSTRAP_POLICY
        if path == "/api/checkout":
            return CHECKOUT_POLICY
        if path in {"/api/pay/tetra98", "/api/pay/crypto/initiate"}:
            return PAYMENT_WRITE_POLICY
        if path == "/api/cashout":
            return CASHOUT_POLICY
        if _REVEAL_CREDENTIAL_PATH.fullmatch(path):
            return CREDENTIAL_REVEAL_POLICY

    if method in {"GET", "HEAD"} and (
        path == "/api" or path.startswith("/api/")
    ):
        return ORDINARY_API_READ_POLICY

    return None


def _canonical_ip(raw_value: str) -> str | None:
    try:
        return ip_address(raw_value).compressed
    except ValueError:
        return None


def _trusted_proxy_peer(peer_host: str) -> bool:
    peer_ip = _canonical_ip(peer_host)
    if peer_ip is None:
        return False
    parsed_peer = ip_address(peer_ip)
    for raw_entry in settings.TRUSTED_PROXY_IPS.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        try:
            if parsed_peer in ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def effective_client_ip(request: Request) -> str | None:
    """Accept one rebuilt client IP only from an explicitly trusted peer."""
    peer_host = request.client.host if request.client else "unknown"
    canonical_peer = _canonical_ip(peer_host)
    if canonical_peer is None:
        return None

    forwarded_values = request.headers.getlist("x-forwarded-for")
    forwarded_for = forwarded_values[0].strip() if len(forwarded_values) == 1 else ""
    if _trusted_proxy_peer(canonical_peer) and "," not in forwarded_for:
        canonical_forwarded = _canonical_ip(forwarded_for)
        if canonical_forwarded is not None:
            return canonical_forwarded

    return canonical_peer


def effective_client_identity(request: Request) -> str:
    client_ip = effective_client_ip(request)
    if client_ip is not None:
        return f"ip:{client_ip}"

    peer_host = request.client.host if request.client else "unknown"
    digest = hashlib.sha256(peer_host.encode("utf-8", errors="replace")).hexdigest()
    return f"peer:{digest[:32]}"


def _configured_networks(
    raw_value: str,
) -> tuple[IPv4Network | IPv6Network, ...]:
    if not raw_value.strip():
        return ()

    entries = raw_value.split(",")
    if any(not entry.strip() or "*" in entry for entry in entries):
        raise ValueError("Callback source allowlists require explicit CIDRs.")

    return tuple(ip_network(entry.strip(), strict=True) for entry in entries)


def callback_source_decision(request: Request) -> CallbackSourceDecision:
    path = request.url.path.rstrip("/")
    if path == "/api/pay/tetra98/callback":
        raw_networks = settings.TETRA98_CALLBACK_ALLOWED_CIDRS
    elif path == "/api/pay/crypto/callback":
        raw_networks = settings.CRYPTO_CALLBACK_ALLOWED_CIDRS
    else:
        return CallbackSourceDecision(configured=False, allowed=True, config_valid=True)

    if not raw_networks.strip():
        return CallbackSourceDecision(configured=False, allowed=True, config_valid=True)

    try:
        networks = _configured_networks(raw_networks)
    except ValueError:
        return CallbackSourceDecision(configured=True, allowed=False, config_valid=False)

    client_ip = effective_client_ip(request)
    if client_ip is None:
        return CallbackSourceDecision(configured=True, allowed=False, config_valid=True)

    parsed_client = ip_address(client_ip)
    return CallbackSourceDecision(
        configured=True,
        allowed=any(parsed_client in network for network in networks),
        config_valid=True,
    )


async def acquire_ingress_slot(policy: IngressPolicy) -> InFlightDecision:
    key = namespaced_key(f"ingress:in-flight:{policy.name}")
    token = secrets.token_urlsafe(24)
    script = (
        "local clock = redis.call('TIME'); "
        "local now_ms = (clock[1] * 1000) + math.floor(clock[2] / 1000); "
        "redis.call('zremrangebyscore', KEYS[1], '-inf', now_ms); "
        "local count = redis.call('zcard', KEYS[1]); "
        "local max_count = tonumber(ARGV[2]); "
        "local ttl_ms = tonumber(ARGV[3]) * 1000; "
        "if count >= max_count then "
        "redis.call('pexpire', KEYS[1], ttl_ms); return {0, count}; end; "
        "redis.call('zadd', KEYS[1], now_ms + ttl_ms, ARGV[1]); "
        "redis.call('pexpire', KEYS[1], ttl_ms); "
        "return {1, count + 1}"
    )
    try:
        result = await redis_client.eval(
            script,
            1,
            key,
            token,
            settings.INGRESS_SENSITIVE_MAX_IN_FLIGHT,
            settings.INGRESS_IN_FLIGHT_TTL_SECONDS,
        )
        allowed = bool(int(result[0]))
    except Exception as exc:
        logger.error(
            "Ingress concurrency guard unavailable for %s: %s",
            policy.name,
            type(exc).__name__,
        )
        return InFlightDecision(allowed=False, backend_available=False)

    return InFlightDecision(
        allowed=allowed,
        backend_available=True,
        lease=IngressLease(key=key, token=token) if allowed else None,
    )


async def release_ingress_slot(lease: IngressLease | None) -> None:
    if lease is None:
        return
    script = (
        "local removed = redis.call('zrem', KEYS[1], ARGV[1]); "
        "if redis.call('zcard', KEYS[1]) == 0 then redis.call('del', KEYS[1]); end; "
        "return removed"
    )
    try:
        await redis_client.eval(script, 1, lease.key, lease.token)
    except Exception as exc:
        logger.error(
            "Ingress concurrency lease release failed: %s",
            type(exc).__name__,
        )


async def check_ingress_request(request: Request) -> IngressDecision:
    policy = ingress_policy(request.method, request.url.path)
    if policy is None:
        return IngressDecision(None, allowed=True, backend_available=True)

    source = callback_source_decision(request)
    if not source.config_valid:
        logger.error("Callback source CIDR configuration is invalid.")
        return IngressDecision(
            policy,
            allowed=False,
            backend_available=False,
            block_reason="callback_source_config_invalid",
        )
    if source.configured and not source.allowed:
        return IngressDecision(
            policy,
            allowed=False,
            backend_available=True,
            block_reason="callback_source_denied",
        )

    try:
        result = await check_rate_limit(
            f"ingress:{policy.name}",
            effective_client_identity(request),
            limit=policy.limit,
            window_seconds=policy.window_seconds,
        )
    except Exception as exc:
        logger.error(
            "Ingress rate-limit check failed for %s: %s",
            policy.name,
            type(exc).__name__,
        )
        result = RateLimitDecision(
            allowed=False,
            count=None,
            backend_available=False,
        )

    if not result.backend_available:
        return IngressDecision(
            policy,
            allowed=False,
            backend_available=False,
            block_reason="limiter_unavailable",
        )
    if not result.allowed:
        return IngressDecision(
            policy,
            allowed=False,
            backend_available=True,
            block_reason="rate_limited",
        )

    if policy.fail_closed:
        in_flight = await acquire_ingress_slot(policy)
        if not in_flight.backend_available:
            return IngressDecision(
                policy,
                allowed=False,
                backend_available=False,
                block_reason="concurrency_guard_unavailable",
            )
        if not in_flight.allowed:
            return IngressDecision(
                policy,
                allowed=False,
                backend_available=True,
                block_reason="concurrency_limited",
            )
        return IngressDecision(
            policy,
            allowed=True,
            backend_available=True,
            lease=in_flight.lease,
        )

    return IngressDecision(
        policy,
        allowed=True,
        backend_available=True,
    )
