from functools import cached_property
from typing import Set

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    DATABASE_URL: str
    REDIS_URL: str = Field(default="redis://redis:6379/0")
    BOT_TOKEN: str
    WEBHOOK_URL: str
    WEBHOOK_SECRET: str
    WEB_APP_URL: str
    BOT_USERNAME: str = Field(default="keshepoolbot")
    TETRA98_API_URL: str = ""
    TETRA98_API_KEY: str = ""
    ADMIN_TELEGRAM_IDS: str = ""
    ADMIN_API_KEY: str = Field(default="")
    ASSET_ROOT: str = "/app/static"
    PUBLIC_ASSET_BASE_URL: str = "/static"
    ALLOW_INSECURE_DEV_AUTH: bool = Field(default=False)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def secure_dev_auth(self):
        if self.ENVIRONMENT.lower() == "production" and self.ALLOW_INSECURE_DEV_AUTH:
            self.ALLOW_INSECURE_DEV_AUTH = False
        return self

    @cached_property
    def admin_ids(self) -> Set[str]:
        return {value.strip() for value in self.ADMIN_TELEGRAM_IDS.split(",") if value.strip()}

    @property
    def tetra98_callback_url(self) -> str:
        return f"{self.WEBHOOK_URL.rstrip('/')}/api/pay/tetra98/callback"

settings = Settings()