from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Validates and loads environment variables required for the bot execution.
    Fails fast if critical variables are missing from the Docker environment.
    """
    DATABASE_URL: str
    ADMIN_BOT_TOKEN: str
    ADMIN_TELEGRAM_IDS: str
    ADMIN_GROUP_CHAT_ID: str

    # Pydantic v2 syntax for environment configuration
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Instantiate the settings to be imported across the application
settings = Settings()