import asyncio
import unittest
from types import SimpleNamespace

from aiogram.enums import ChatMemberStatus
from pydantic import ValidationError

from app.bot.filters import IsAdminFilter
from app.core.config import Settings, settings


def settings_values(**overrides):
    values = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql+asyncpg://user:password@db/test",
        "BOT_TOKEN": "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "ADMIN_BOT_TOKEN": "123457:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "WEBHOOK_URL": "https://example.test",
        "WEBHOOK_SECRET": "test-webhook-secret",
        "WEB_APP_URL": "https://example.test",
        "ADMIN_API_KEY": "test-admin-key",
        "ADMIN_TELEGRAM_IDS": "123456",
        "ADMIN_REPORT_LANGUAGE": "fa",
        "USDT_TO_IRR_RATE": 85000,
    }
    values.update(overrides)
    return values


class FakeBot:
    def __init__(self, status):
        self.status = status
        self.calls = []

    async def get_chat_member(self, chat_id, user_id):
        self.calls.append((chat_id, user_id))
        return SimpleNamespace(status=self.status)


class AdminSettingsTests(unittest.TestCase):
    def test_admin_ids_have_one_canonical_source(self):
        configured = Settings(**settings_values(ADMIN_TELEGRAM_IDS="123, 456"))
        self.assertEqual(configured.admin_ids, {"123", "456"})

    def test_production_requires_an_explicit_admin(self):
        with self.assertRaisesRegex(ValidationError, "ADMIN_TELEGRAM_IDS"):
            Settings(**settings_values(ENVIRONMENT="production", ADMIN_TELEGRAM_IDS=""))

    def test_enabled_payment_methods_require_safe_production_config(self):
        with self.assertRaisesRegex(ValidationError, "TETRA98_API_URL"):
            Settings(
                **settings_values(
                    ENVIRONMENT="production",
                    TETRA98_API_KEY="enabled",
                    TETRA98_API_URL="http://payment.example.test",
                )
            )

        configured = Settings(
            **settings_values(
                ENVIRONMENT="production",
                TETRA98_API_KEY="enabled",
                TETRA98_API_URL="https://payment.example.test",
                TETRA98_WEBHOOK_SECRET="",
            )
        )
        self.assertEqual(configured.TETRA98_API_URL, "https://payment.example.test")

        with self.assertRaisesRegex(ValidationError, "CRYPTO_WEBHOOK_SECRET"):
            Settings(
                **settings_values(
                    ENVIRONMENT="production",
                    CRYPTO_DEPOSIT_ADDRESS_USDT="configured-address",
                    CRYPTO_WEBHOOK_SECRET="",
                )
            )

    def test_production_requires_explicit_rate_fallback(self):
        values = settings_values(ENVIRONMENT="production")
        values.pop("USDT_TO_IRR_RATE")
        with self.assertRaisesRegex(ValidationError, "USDT_TO_IRR_RATE"):
            Settings(**values)

    def test_production_requires_telegram_webhook_secret(self):
        with self.assertRaisesRegex(ValidationError, "WEBHOOK_SECRET"):
            Settings(**settings_values(ENVIRONMENT="production", WEBHOOK_SECRET=""))

    def test_production_rejects_insecure_development_auth(self):
        with self.assertRaisesRegex(ValidationError, "ALLOW_INSECURE_DEV_AUTH"):
            Settings(
                **settings_values(
                    ENVIRONMENT="production",
                    ALLOW_INSECURE_DEV_AUTH=True,
                )
            )

    def test_group_chat_id_must_be_negative(self):
        with self.assertRaisesRegex(ValidationError, "negative Telegram group chat ID"):
            Settings(**settings_values(ADMIN_GROUP_CHAT_ID="123456"))

    def test_cache_namespace_includes_the_environment(self):
        configured = Settings(**settings_values(CACHE_NAMESPACE="keshepool", ENVIRONMENT="staging"))
        self.assertEqual(configured.cache_namespace, "keshepool:staging")

    def test_admin_report_language_accepts_only_supported_values(self):
        self.assertEqual(Settings(**settings_values(ADMIN_REPORT_LANGUAGE="en")).ADMIN_REPORT_LANGUAGE, "en")
        with self.assertRaises(ValidationError):
            Settings(**settings_values(ADMIN_REPORT_LANGUAGE="de"))


class AdminFilterTests(unittest.TestCase):
    def setUp(self):
        self.previous_admin_ids = settings.__dict__.get("admin_ids")
        self.previous_group_id = settings.ADMIN_GROUP_CHAT_ID
        settings.__dict__["admin_ids"] = {"42"}
        settings.ADMIN_GROUP_CHAT_ID = "-100123"

    def tearDown(self):
        if self.previous_admin_ids is None:
            settings.__dict__.pop("admin_ids", None)
        else:
            settings.__dict__["admin_ids"] = self.previous_admin_ids
        settings.ADMIN_GROUP_CHAT_ID = self.previous_group_id

    def event(self, user_id, chat_id, chat_type, status):
        return SimpleNamespace(
            from_user=SimpleNamespace(id=user_id),
            chat=SimpleNamespace(id=chat_id, type=chat_type),
            bot=FakeBot(status),
        )

    def authorize(self, event):
        return asyncio.run(IsAdminFilter()(event))

    def test_explicit_admin_can_use_private_chat(self):
        event = self.event(42, 42, "private", ChatMemberStatus.MEMBER)
        self.assertTrue(self.authorize(event))
        self.assertEqual(event.bot.calls, [])

    def test_non_allowlisted_private_user_is_denied(self):
        event = self.event(99, 99, "private", ChatMemberStatus.MEMBER)
        self.assertFalse(self.authorize(event))
        self.assertEqual(event.bot.calls, [])

    def test_ordinary_group_member_is_denied(self):
        event = self.event(42, -100123, "supergroup", ChatMemberStatus.MEMBER)
        self.assertFalse(self.authorize(event))

    def test_explicit_group_admin_is_allowed(self):
        event = self.event(42, -100123, "supergroup", ChatMemberStatus.ADMINISTRATOR)
        self.assertTrue(self.authorize(event))
        self.assertEqual(event.bot.calls, [(-100123, 42)])

    def test_unlisted_group_admin_is_denied_without_lookup(self):
        event = self.event(99, -100123, "supergroup", ChatMemberStatus.ADMINISTRATOR)
        self.assertFalse(self.authorize(event))
        self.assertEqual(event.bot.calls, [])

    def test_admin_in_an_unconfigured_group_is_denied(self):
        event = self.event(42, -100999, "supergroup", ChatMemberStatus.ADMINISTRATOR)
        self.assertFalse(self.authorize(event))
        self.assertEqual(event.bot.calls, [])
