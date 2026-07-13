import os
import tempfile
from pathlib import Path


TEST_ENV = {
    "ENVIRONMENT": "test",
    "DATABASE_URL": os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test:test@127.0.0.1:5432/keshepool_test",
    ),
    "REDIS_URL": "redis://127.0.0.1:6399/15",
    "BOT_TOKEN": "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "ADMIN_BOT_TOKEN": "123457:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
    "WEBHOOK_URL": "https://example.test",
    "WEBHOOK_SECRET": "test-webhook-secret",
    "WEB_APP_URL": "https://example.test",
    "ADMIN_API_KEY": "test-admin-key",
    "ADMIN_TELEGRAM_IDS": "123456",
    "TETRA98_API_URL": "https://pay.example.test",
    "ASSET_ROOT": str(Path(tempfile.gettempdir()) / "keshepool-test-static"),
}

for key, value in TEST_ENV.items():
    os.environ[key] = value
