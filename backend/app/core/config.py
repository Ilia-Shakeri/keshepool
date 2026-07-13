from functools import cached_property
from typing import Set
from urllib.parse import urlparse

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    DATABASE_URL: str
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    BOT_TOKEN: str
    ADMIN_BOT_TOKEN: str
    WEBHOOK_URL: str
    WEBHOOK_SECRET: str
    WEB_APP_URL: str
    BOT_USERNAME: str = Field(default="keshepoolbot")
    TETRA98_API_URL: str = ""
    TETRA98_API_KEY: str = ""
    TETRA98_WEBHOOK_SECRET: str = ""
    CRYPTO_WEBHOOK_SECRET: str = ""
    CRYPTO_DEPOSIT_ADDRESS_USDT: str = ""
    ADMIN_TELEGRAM_IDS: str = ""
    ADMIN_GROUP_CHAT_ID: str = ""
    ADMIN_API_KEY: str = Field(default="")
    ASSET_ROOT: str = "/app/static"
    PUBLIC_ASSET_BASE_URL: str = "/static"
    SUPPORT_TELEGRAM_USERNAME: str = ""
    ALLOW_INSECURE_DEV_AUTH: bool = Field(default=False)
    TELEGRAM_AUTH_MAX_AGE_SECONDS: int = Field(default=86400, ge=60)
    TELEGRAM_AUTH_FUTURE_SKEW_SECONDS: int = Field(default=60, ge=0)
    USER_LAST_SEEN_WRITE_INTERVAL_SECONDS: int = Field(default=300, ge=60)
    CACHE_NAMESPACE: str = Field(default="keshepool", min_length=1)
    REDIS_CONNECT_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0)
    REDIS_SOCKET_TIMEOUT_SECONDS: float = Field(default=2.0, gt=0)
    USDT_TO_IRR_RATE: int = Field(default=85000, description="USDT to تومان exchange rate (تومان per 1 USDT)")
    TETRA98_SIG_HEADER: str = Field(default="X-Tetra98-Signature", description="Header name Tetra98 uses for HMAC signature")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production_security(self):
        # Fail fast when production security settings cannot verify privileged calls.
        if self.ENVIRONMENT.lower() == "production":
            if self.ALLOW_INSECURE_DEV_AUTH:
                raise ValueError("ALLOW_INSECURE_DEV_AUTH cannot be enabled in production.")

            if not self.WEBHOOK_SECRET:
                raise ValueError("WEBHOOK_SECRET must be configured in production.")
            
            if not self.ADMIN_API_KEY:
                raise ValueError("ADMIN_API_KEY must be defined and strictly set in the production environment to prevent unauthorized internal access.")

            if not self.admin_ids:
                raise ValueError("ADMIN_TELEGRAM_IDS must contain at least one numeric Telegram user ID in production.")

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

settings = Settings()
