import hmac
import logging
from functools import cached_property
from typing import Literal, Set
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    DATABASE_URL: str
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    BOT_TOKEN: str
    ADMIN_BOT_TOKEN: str
    TELEGRAM_BOT_MODE: Literal["webhook", "polling", "disabled"] = "webhook"
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""
    MAIN_TELEGRAM_WEBHOOK_SECRET: str = ""
    ADMIN_TELEGRAM_WEBHOOK_SECRET: str = ""
    WEB_APP_URL: str
    BOT_USERNAME: str = Field(default="keshepoolbot")
    TETRA98_API_URL: str = ""
    TETRA98_API_KEY: str = ""
    TETRA98_WEBHOOK_SECRET: str = ""
    CRYPTO_WEBHOOK_SECRET: str = ""
    CRYPTO_DEPOSIT_ADDRESS_USDT: str = ""
    ADMIN_TELEGRAM_IDS: str = ""
    ADMIN_GROUP_CHAT_ID: str = ""
    ADMIN_REQUIRE_GROUP_ADMIN: bool = Field(default=False)
    ADMIN_RBAC_ENABLED: bool = Field(default=False)
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
    TRUSTED_PROXY_IPS: str = Field(default="127.0.0.1")
    CSP_REPORT_ONLY: bool = Field(default=True)
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

        if not self.CACHE_NAMESPACE.strip().strip(":"):
            raise ValueError("CACHE_NAMESPACE must contain a non-empty application name.")

        if not self.TRUSTED_PROXY_IPS.strip() or "*" in self.TRUSTED_PROXY_IPS:
            raise ValueError("TRUSTED_PROXY_IPS must list explicit proxy addresses or networks.")

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
