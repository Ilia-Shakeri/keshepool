import asyncio
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import Session

from app.bot.handlers import admin_panel
from app.bot.services import scheduler
from app.models import InventoryItem, ItemStatus


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


class FakeSessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def test_low_stock_counts_only_usable_inventory_and_keeps_empty_variants():
    engine = create_engine("sqlite://")
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE product_variants ("
            "id VARCHAR PRIMARY KEY, product_id VARCHAR NOT NULL, duration VARCHAR NOT NULL, "
            "price_label VARCHAR NOT NULL, raw_price NUMERIC NOT NULL, is_active BOOLEAN NOT NULL)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE inventory_items ("
            "id INTEGER PRIMARY KEY, product_id VARCHAR NOT NULL, variant_id VARCHAR NOT NULL, "
            "credentials TEXT NOT NULL, status VARCHAR NOT NULL, assigned_to_user_id INTEGER, "
            "expires_at DATETIME, assigned_at DATETIME, created_at DATETIME NOT NULL)"
        )
        variants = [
            ("zero", True),
            ("two", True),
            ("three", True),
            ("four", True),
            ("expired", True),
            ("fresh", True),
            ("wrong-status", True),
            ("no-rows", True),
            ("inactive", False),
        ]
        for variant_id, active in variants:
            connection.exec_driver_sql(
                "INSERT INTO product_variants "
                "(id, product_id, duration, price_label, raw_price, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                (variant_id, "product", "1 month", "test", 1, active),
            )

        rows = []

        def add(variant_id, status=ItemStatus.AVAILABLE, expires_at=None):
            rows.append(
                {
                    "product_id": "product",
                    "variant_id": variant_id,
                    "credentials": f"{variant_id}-{len(rows)}",
                    "status": status,
                    "expires_at": expires_at,
                    "created_at": now,
                }
            )

        add("zero", ItemStatus.RESERVED)
        for _ in range(2):
            add("two")
        for _ in range(3):
            add("three")
        for _ in range(4):
            add("four")
        add("expired", expires_at=now - timedelta(seconds=1))
        add("fresh", expires_at=now + timedelta(hours=1))
        for status in (ItemStatus.ASSIGNED, ItemStatus.RESERVED, ItemStatus.DISABLED):
            add("wrong-status", status=status)
        add("inactive")
        connection.execute(insert(InventoryItem.__table__), rows)

    with Session(engine) as sync_session:
        warnings = asyncio.run(scheduler._check_low_stock(AsyncSessionAdapter(sync_session)))

    by_variant = {line.split(" / ", 1)[0].split()[-1]: line for line in warnings}
    assert "zero" in by_variant and ": 0 remaining" in by_variant["zero"]
    assert "two" in by_variant and ": 2 remaining" in by_variant["two"]
    assert "three" in by_variant and ": 3 remaining" in by_variant["three"]
    assert "four" not in by_variant
    assert "expired" in by_variant and ": 0 remaining" in by_variant["expired"]
    assert "fresh" in by_variant and ": 1 remaining" in by_variant["fresh"]
    assert "wrong-status" in by_variant and ": 0 remaining" in by_variant["wrong-status"]
    assert "no-rows" in by_variant and ": 0 remaining" in by_variant["no-rows"]
    assert "inactive" not in by_variant


def configure_report_test(monkeypatch, report_text="report"):
    build_report = AsyncMock(return_value=report_text)
    monkeypatch.setattr(admin_panel, "build_report_text", build_report)
    monkeypatch.setattr(scheduler, "AsyncSessionLocal", FakeSessionContext)
    monkeypatch.setattr(scheduler, "_check_low_stock", AsyncMock(return_value=[]))
    monkeypatch.setattr(scheduler.settings, "ADMIN_GROUP_CHAT_ID", "-100123")
    monkeypatch.setattr(scheduler.settings, "ADMIN_REPORT_LANGUAGE", "en")
    return build_report


def test_scheduler_passes_configured_report_language(monkeypatch):
    build_report = configure_report_test(monkeypatch)
    bot = AsyncMock()
    asyncio.run(scheduler.send_hourly_report(bot))
    build_report.assert_awaited_once_with("en")


def test_report_generation_failure_is_reraised(monkeypatch):
    build_report = configure_report_test(monkeypatch)
    build_report.side_effect = RuntimeError("report failed")
    with pytest.raises(RuntimeError, match="report failed"):
        asyncio.run(scheduler.send_hourly_report(AsyncMock()))


def test_telegram_delivery_failure_is_reraised(monkeypatch):
    configure_report_test(monkeypatch)
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("delivery failed")
    with pytest.raises(RuntimeError, match="delivery failed"):
        asyncio.run(scheduler.send_hourly_report(bot))


def test_successful_delivery_logs_success(monkeypatch, caplog):
    configure_report_test(monkeypatch)
    with caplog.at_level(logging.INFO, logger=scheduler.__name__):
        asyncio.run(scheduler.send_hourly_report(AsyncMock()))
    assert "Hourly report dispatched successfully." in caplog.text
