import hmac
import logging
from functools import cached_property
from ipaddress import ip_network
from pathlib import Path
from typing import Literal, Set
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DATABASE_MAX_OVERFLOW: int = Field(default=10, ge=0, le=100)
    DATABASE_POOL_TIMEOUT_SECONDS: int = Field(default=5, ge=1, le=60)
    DATABASE_POOL_RECYCLE_SECONDS: int = Field(default=1800, ge=60, le=86400)
    DATABASE_STATEMENT_TIMEOUT_MS: int = Field(default=30_000, ge=1000, le=300_000)
    DATABASE_LOCK_TIMEOUT_MS: int = Field(default=5_000, ge=100, le=60_000)
    DATABASE_IDLE_TRANSACTION_TIMEOUT_MS: int = Field(
        default=30_000,
        ge=1000,
        le=300_000,
    )
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    BOT_TOKEN: str
    ADMIN_BOT_TOKEN: str
    TELEGRAM_BOT_MODE: Literal["webhook", "polling", "disabled"] = "webhook"
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""
    MAIN_TELEGRAM_WEBHOOK_SECRET: str = ""
    ADMIN_TELEGRAM_WEBHOOK_SECRET: str = ""
    WEB_APP_URL: str
    BOT_USERNAME: str = Field(
        default="keshepoolbot",
        min_length=5,
        max_length=32,
        pattern=r"^[A-Za-z0-9_]+$",
    )
    TETRA98_API_URL: str = ""
    TETRA98_API_KEY: str = ""
    TETRA98_WEBHOOK_SECRET: str = ""
    TETRA98_ENABLED: bool = Field(default=False)
    CARD_TO_CARD_ENABLED: bool = Field(default=True)
    CARD_TO_CARD_NUMBER: str = Field(default="6219861456548642")
    CARD_TO_CARD_HOLDER: str = Field(default="مهدیار کریم زاده", min_length=2, max_length=100)
    CARD_TRANSFER_MAX_RECEIPT_BYTES: int = Field(default=5_000_000, ge=100_000, le=10_000_000)
    CARD_TRANSFER_ADMIN_NOTIFY_MAX_ATTEMPTS: int = Field(default=12, ge=1, le=100)
    CRYPTO_WEBHOOK_SECRET: str = ""
    CRYPTO_DEPOSIT_ADDRESS_USDT: str = ""
    ADMIN_TELEGRAM_IDS: str = ""
    ADMIN_GROUP_CHAT_ID: str = ""
    ADMIN_REQUIRE_GROUP_ADMIN: bool = Field(default=False)
    ADMIN_RBAC_ENABLED: bool = Field(default=False)
    ADMIN_ENV_BREAK_GLASS_ENABLED: bool = Field(default=True)
    ADMIN_DUAL_APPROVAL_ENABLED: bool = Field(default=False)
    ADMIN_DUAL_APPROVAL_WALLET_THRESHOLD_TOMAN: int = Field(default=10_000_000, ge=1)
    ADMIN_DUAL_APPROVAL_RATE_DEVIATION_PERCENT: int = Field(default=10, ge=1, le=100)
    ADMIN_REPORT_LANGUAGE: Literal["fa", "en"] = "fa"
    ADMIN_FSM_TTL_SECONDS: int = Field(default=3600, ge=300, le=86400)
    TZ: str = "Asia/Tehran"
    ADMIN_API_KEY: str = Field(default="")
    ENABLE_INTERNAL_ADMIN_API: bool = Field(default=False)
    ASSET_ROOT: str = "/app/static"
    PUBLIC_ASSET_BASE_URL: str = "/static"
    SUPPORT_TELEGRAM_USERNAME: str = ""
    ALLOW_INSECURE_DEV_AUTH: bool = Field(default=False)
    TELEGRAM_AUTH_MAX_AGE_SECONDS: int = Field(default=3600, ge=300, le=86400)
    TELEGRAM_FINANCIAL_AUTH_MAX_AGE_SECONDS: int = Field(default=300, ge=60, le=900)
    AUTH_SESSION_EPOCH: str = Field(default="1", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    TELEGRAM_AUTH_FUTURE_SKEW_SECONDS: int = Field(default=60, ge=0)
    TELEGRAM_INIT_DATA_MAX_BYTES: int = Field(default=8192, ge=1024, le=65536)
    TELEGRAM_WEBHOOK_MAX_BYTES: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    TELEGRAM_WEBHOOK_MAX_JSON_DEPTH: int = Field(default=32, ge=4, le=128)
    TELEGRAM_INBOX_BATCH_SIZE: int = Field(default=20, ge=1, le=100)
    TELEGRAM_INBOX_POLL_SECONDS: float = Field(default=0.5, ge=0.1, le=10)
    TELEGRAM_INBOX_STALE_SECONDS: int = Field(default=300, ge=30, le=3600)
    TELEGRAM_INBOX_MAX_ATTEMPTS: int = Field(default=8, ge=1, le=50)
    TELEGRAM_INBOX_RETRY_SECONDS: int = Field(default=10, ge=1, le=600)
    USER_LAST_SEEN_WRITE_INTERVAL_SECONDS: int = Field(default=300, ge=60)
    CACHE_NAMESPACE: str = Field(default="keshepool", min_length=1)
    CATALOG_CACHE_TTL_SECONDS: int = Field(default=30, ge=5, le=300)
    CATALOG_CACHE_LOCK_TTL_SECONDS: int = Field(default=5, ge=1, le=30)
    REDIS_CONNECT_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0)
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0)
    REDIS_MAX_CONNECTIONS: int = Field(default=50, ge=5, le=1000)
    REDIS_RETRY_ATTEMPTS: int = Field(default=3, ge=0, le=10)
    REDIS_RETRY_BACKOFF_MAX_SECONDS: float = Field(default=1.0, ge=0.05, le=10.0)
    TRUSTED_PROXY_IPS: str = Field(default="127.0.0.1")
    INGRESS_SENSITIVE_MAX_IN_FLIGHT: int = Field(default=64, ge=1, le=10_000)
    INGRESS_IN_FLIGHT_TTL_SECONDS: int = Field(default=120, ge=5, le=3600)
    TETRA98_CALLBACK_ALLOWED_CIDRS: str = Field(default="")
    CRYPTO_CALLBACK_ALLOWED_CIDRS: str = Field(default="")
    CREDENTIAL_VAULT_DUAL_WRITE_ENABLED: bool = Field(default=False)
    CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED: bool = Field(default=False)
    CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED: bool = Field(default=True)
    CREDENTIAL_VAULT_FINALIZE_ENABLED: bool = Field(default=False)
    CREDENTIAL_VAULT_ENCRYPTION_KEYS_FILE: str = Field(default="")
    CREDENTIAL_VAULT_FINGERPRINT_KEY_FILE: str = Field(default="")
    CREDENTIAL_REVEAL_MAX_PER_ORDER: int = Field(default=5, ge=1, le=100)
    CSP_REPORT_ONLY: bool = Field(default=True)
    OPERATIONS_RATE_DB_ENABLED: bool = Field(default=False)
    USDT_TO_IRR_RATE: int = Field(default=85000, description="USDT to تومان exchange rate (تومان per 1 USDT)")
    TETRA98_SIG_HEADER: str = Field(default="X-Tetra98-Signature", description="Header name Tetra98 uses for HMAC signature")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production_security(self):
        # Fail fast when production security settings cannot verify privileged calls.
        if self.ENVIRONMENT.lower() == "production":
            if self.TELEGRAM_BOT_MODE != "webhook":
                raise ValueError("TELEGRAM_BOT_MODE must be webhook in production.")

            if self.ALLOW_INSECURE_DEV_AUTH:
                raise ValueError("ALLOW_INSECURE_DEV_AUTH cannot be enabled in production.")

            if not self.MAIN_TELEGRAM_WEBHOOK_SECRET.strip():
                raise ValueError("MAIN_TELEGRAM_WEBHOOK_SECRET must be configured in production.")
            if not self.ADMIN_TELEGRAM_WEBHOOK_SECRET.strip():
                raise ValueError("ADMIN_TELEGRAM_WEBHOOK_SECRET must be configured in production.")
            if hmac.compare_digest(
                self.MAIN_TELEGRAM_WEBHOOK_SECRET.strip(),
                self.ADMIN_TELEGRAM_WEBHOOK_SECRET.strip(),
            ):
                raise ValueError("Main and admin Telegram webhook secrets must differ in production.")

            webhook_url = urlparse(self.WEBHOOK_URL.strip())
            if webhook_url.scheme != "https" or not webhook_url.netloc:
                raise ValueError("WEBHOOK_URL must be an explicit HTTPS URL in production.")
            
            if self.ENABLE_INTERNAL_ADMIN_API and not self.ADMIN_API_KEY:
                raise ValueError(
                    "ADMIN_API_KEY is required when ENABLE_INTERNAL_ADMIN_API is enabled."
                )

            if not self.admin_ids:
                raise ValueError("ADMIN_TELEGRAM_IDS must contain at least one numeric Telegram user ID in production.")

            if self.ADMIN_GROUP_CHAT_ID and not self.ADMIN_REQUIRE_GROUP_ADMIN:
                raise ValueError("ADMIN_REQUIRE_GROUP_ADMIN must be enabled for production group operation.")

            web_app_url = urlparse(self.WEB_APP_URL.strip())
            if (
                web_app_url.scheme != "https"
                or not web_app_url.netloc
                or web_app_url.username
                or web_app_url.password
                or web_app_url.fragment
            ):
                raise ValueError("WEB_APP_URL must be a safe explicit HTTPS URL in production.")

            if self.TETRA98_API_KEY:
                tetra98_url = urlparse(self.TETRA98_API_URL.strip())
                if tetra98_url.scheme != "https" or not tetra98_url.netloc:
                    raise ValueError(
                        "TETRA98_API_URL must be an explicit HTTPS URL when TETRA98_API_KEY is configured in production."
                    )

            if self.CRYPTO_DEPOSIT_ADDRESS_USDT and not self.CRYPTO_WEBHOOK_SECRET:
                raise ValueError("CRYPTO_WEBHOOK_SECRET is required when CRYPTO_DEPOSIT_ADDRESS_USDT is configured in production.")

            if (
                "USDT_TO_IRR_RATE" not in self.model_fields_set
                or self.USDT_TO_IRR_RATE <= 0
            ):
                raise ValueError(
                    "USDT_TO_IRR_RATE must be explicitly set to a positive operator-reviewed fallback in production."
                )

        invalid_admin_ids = [value for value in self._admin_id_values() if not value.isdigit()]
        if invalid_admin_ids:
            raise ValueError("ADMIN_TELEGRAM_IDS must contain comma-separated numeric Telegram user IDs.")

        if self.ADMIN_GROUP_CHAT_ID and not self.ADMIN_GROUP_CHAT_ID.lstrip("-").isdigit():
            raise ValueError("ADMIN_GROUP_CHAT_ID must be a numeric Telegram chat ID.")

        if self.ADMIN_GROUP_CHAT_ID and not self.ADMIN_GROUP_CHAT_ID.startswith("-"):
            raise ValueError("ADMIN_GROUP_CHAT_ID must be a negative Telegram group chat ID.")

        if self.ADMIN_DUAL_APPROVAL_ENABLED and not self.ADMIN_GROUP_CHAT_ID:
            raise ValueError("ADMIN_GROUP_CHAT_ID is required when dual approval is enabled.")

        if self.ADMIN_DUAL_APPROVAL_ENABLED and not self.OPERATIONS_RATE_DB_ENABLED:
            raise ValueError("OPERATIONS_RATE_DB_ENABLED is required when dual approval is enabled.")

        if self.ADMIN_DUAL_APPROVAL_ENABLED and not self.ADMIN_RBAC_ENABLED:
            raise ValueError("ADMIN_RBAC_ENABLED is required when dual approval is enabled.")

        card_number = "".join(self.CARD_TO_CARD_NUMBER.split())
        if self.CARD_TO_CARD_ENABLED:
            if not card_number.isdigit() or len(card_number) != 16:
                raise ValueError("CARD_TO_CARD_NUMBER must contain exactly 16 digits.")
            checksum = 0
            for index, raw_digit in enumerate(card_number):
                digit = int(raw_digit)
                if index % 2 == 0:
                    digit *= 2
                    if digit > 9:
                        digit -= 9
                checksum += digit
            if checksum % 10:
                raise ValueError("CARD_TO_CARD_NUMBER checksum is invalid.")
            if not self.CARD_TO_CARD_HOLDER.strip():
                raise ValueError("CARD_TO_CARD_HOLDER is required when card transfer is enabled.")
            if self.ENVIRONMENT.lower() == "production":
                if not self.admin_ids:
                    raise ValueError("ADMIN_TELEGRAM_IDS is required when card transfer is enabled.")
                if not self.ADMIN_GROUP_CHAT_ID:
                    raise ValueError("ADMIN_GROUP_CHAT_ID is required when card transfer is enabled.")

        if not self.ADMIN_ENV_BREAK_GLASS_ENABLED and not self.ADMIN_RBAC_ENABLED:
            raise ValueError("ADMIN_RBAC_ENABLED is required when environment break-glass access is disabled.")

        if not self.CACHE_NAMESPACE.strip().strip(":"):
            raise ValueError("CACHE_NAMESPACE must contain a non-empty application name.")

        if self.DATABASE_LOCK_TIMEOUT_MS >= self.DATABASE_STATEMENT_TIMEOUT_MS:
            raise ValueError(
                "DATABASE_LOCK_TIMEOUT_MS must be lower than DATABASE_STATEMENT_TIMEOUT_MS."
            )

        trusted_proxy_entries = self.TRUSTED_PROXY_IPS.split(",")
        if (
            not self.TRUSTED_PROXY_IPS.strip()
            or any(
                not entry.strip() or "*" in entry
                for entry in trusted_proxy_entries
            )
        ):
            raise ValueError("TRUSTED_PROXY_IPS must list explicit proxy addresses or networks.")
        try:
            for entry in trusted_proxy_entries:
                ip_network(entry.strip(), strict=True)
        except ValueError as exc:
            raise ValueError(
                "TRUSTED_PROXY_IPS must contain valid exact IPv4 or IPv6 addresses or networks."
            ) from exc

        for field_name in (
            "TETRA98_CALLBACK_ALLOWED_CIDRS",
            "CRYPTO_CALLBACK_ALLOWED_CIDRS",
        ):
            raw_networks = getattr(self, field_name)
            if not raw_networks.strip():
                continue
            entries = raw_networks.split(",")
            if any(not entry.strip() or "*" in entry for entry in entries):
                raise ValueError(f"{field_name} must list explicit CIDRs.")
            try:
                for entry in entries:
                    ip_network(entry.strip(), strict=True)
            except ValueError as exc:
                raise ValueError(
                    f"{field_name} must contain valid exact IPv4 or IPv6 CIDRs."
                ) from exc

        vault_runtime_enabled = any(
            (
                self.CREDENTIAL_VAULT_DUAL_WRITE_ENABLED,
                self.CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED,
                self.CREDENTIAL_VAULT_FINALIZE_ENABLED,
            )
        )
        if vault_runtime_enabled:
            for field_name in (
                "CREDENTIAL_VAULT_ENCRYPTION_KEYS_FILE",
                "CREDENTIAL_VAULT_FINGERPRINT_KEY_FILE",
            ):
                configured_path = getattr(self, field_name).strip()
                if not configured_path or not Path(configured_path).is_absolute():
                    raise ValueError(
                        f"{field_name} must be an absolute mounted secret path when the credential vault is enabled."
                    )

        if (
            not self.CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED
            and not self.CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED
        ):
            raise ValueError(
                "CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED cannot be disabled before encrypted reads are enabled."
            )

        if self.CREDENTIAL_VAULT_FINALIZE_ENABLED and not (
            self.CREDENTIAL_VAULT_DUAL_WRITE_ENABLED
            and self.CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED
            and not self.CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED
        ):
            raise ValueError(
                "Credential vault finalization requires dual writes, encrypted reads, and disabled legacy fallback."
            )

        if self.TELEGRAM_BOT_MODE == "webhook":
            if not self.WEBHOOK_URL.strip():
                raise ValueError("WEBHOOK_URL is required in webhook mode.")
            if not self.main_telegram_webhook_secret:
                raise ValueError("Main Telegram webhook secret is required in webhook mode.")
            if not self.admin_telegram_webhook_secret:
                raise ValueError("Admin Telegram webhook secret is required in webhook mode.")

        if (
            self.ENVIRONMENT.lower() != "production"
            and self.WEBHOOK_SECRET.strip()
            and (
                not self.MAIN_TELEGRAM_WEBHOOK_SECRET.strip()
                or not self.ADMIN_TELEGRAM_WEBHOOK_SECRET.strip()
            )
        ):
            logger.warning(
                "WEBHOOK_SECRET compatibility fallback is deprecated; configure separate main and admin secrets."
            )

        return self

    def _admin_id_values(self) -> Set[str]:
        return {value.strip() for value in self.ADMIN_TELEGRAM_IDS.split(",") if value.strip()}

    @cached_property
    def admin_ids(self) -> Set[str]:
        return self._admin_id_values()

    @property
    def card_to_card_number(self) -> str:
        return "".join(self.CARD_TO_CARD_NUMBER.split())

    @property
    def card_transfer_notification_chat_ids(self) -> tuple[str, ...]:
        targets = set(self.admin_ids)
        if self.ADMIN_GROUP_CHAT_ID:
            targets.add(self.ADMIN_GROUP_CHAT_ID)
        return tuple(sorted(targets))

    @property
    def card_to_card_ready(self) -> bool:
        return bool(
            self.CARD_TO_CARD_ENABLED
            and self.card_to_card_number
            and self.CARD_TO_CARD_HOLDER.strip()
            and self.admin_ids
            and self.ADMIN_GROUP_CHAT_ID
        )

    @cached_property
    def cache_namespace(self) -> str:
        app_name = self.CACHE_NAMESPACE.strip().strip(":")
        environment = self.ENVIRONMENT.strip().lower().strip(":")
        return f"{app_name}:{environment}"

    @property
    def tetra98_callback_url(self) -> str:
        return f"{self.WEBHOOK_URL.rstrip('/')}/api/pay/tetra98/callback"

    @property
    def main_telegram_webhook_secret(self) -> str:
        configured = self.MAIN_TELEGRAM_WEBHOOK_SECRET.strip()
        if configured:
            return configured
        return self.WEBHOOK_SECRET.strip() if self.ENVIRONMENT.lower() != "production" else ""

    @property
    def admin_telegram_webhook_secret(self) -> str:
        configured = self.ADMIN_TELEGRAM_WEBHOOK_SECRET.strip()
        if configured:
            return configured
        return self.WEBHOOK_SECRET.strip() if self.ENVIRONMENT.lower() != "production" else ""

    @property
    def web_app_origin(self) -> str:
        parsed = urlparse(self.WEB_APP_URL.strip())
        return f"{parsed.scheme}://{parsed.netloc}"

settings = Settings()
