import asyncio
import os

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, InventoryItem, ItemStatus, Product, ProductVariant
from app.services.credential_vault import CredentialCipher, CredentialVaultError
from app.services.credential_vault_migration import (
    BACKFILL_CONFIRMATION,
    FINALIZE_CONFIRMATION,
    VERIFY_CONFIRMATION,
    backfill_credential_vault_batch,
    finalize_credential_vault_batch,
    verify_credential_vault_batch,
)


RUN_POSTGRES = os.environ.get("KESHEPOOL_RUN_POSTGRES_TESTS") == "1"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not RUN_POSTGRES or not TEST_DATABASE_URL,
    reason="Set KESHEPOOL_RUN_POSTGRES_TESTS=1 with a disposable TEST_DATABASE_URL.",
)


class _MemoryKeys:
    active_version = "v1"

    def encryption_key(self, version: str) -> bytes:
        if version != "v1":
            raise CredentialVaultError("Unknown test key.")
        return b"E" * 32

    def fingerprint_key(self) -> bytes:
        return b"F" * 32


def _assert_disposable_database() -> None:
    database_name = make_url(TEST_DATABASE_URL).database or ""
    if "test" not in database_name.lower():
        raise AssertionError("TEST_DATABASE_URL database name must contain 'test'.")


def test_real_postgres_vault_backfill_duplicate_verify_and_finalize() -> None:
    _assert_disposable_database()

    async def scenario():
        engine = create_async_engine(TEST_DATABASE_URL)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        cipher = CredentialCipher(_MemoryKeys())
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.drop_all)
                await connection.run_sync(Base.metadata.create_all)
            async with sessions() as session:
                session.add(
                    Product(
                        id="vault-product",
                        title="Vault Product",
                        brand="Vault Brand",
                        category="tools",
                    )
                )
                session.add_all(
                    [
                        ProductVariant(
                            id="vault-variant-one",
                            product_id="vault-product",
                            duration="one",
                            price_label="100",
                            raw_price=100,
                        ),
                        ProductVariant(
                            id="vault-variant-two",
                            product_id="vault-product",
                            duration="two",
                            price_label="100",
                            raw_price=100,
                        ),
                    ]
                )
                await session.flush()
                session.add_all(
                    [
                        InventoryItem(
                            product_id="vault-product",
                            variant_id="vault-variant-one",
                            credentials="duplicate-fixture-value",
                            status=ItemStatus.AVAILABLE,
                        ),
                        InventoryItem(
                            product_id="vault-product",
                            variant_id="vault-variant-two",
                            credentials="duplicate-fixture-value",
                            status=ItemStatus.AVAILABLE,
                        ),
                    ]
                )
                await session.commit()

            async with sessions() as session:
                backfill = await backfill_credential_vault_batch(
                    session,
                    cipher,
                    batch_size=50,
                    apply=True,
                    confirmation=BACKFILL_CONFIRMATION,
                )
                await session.commit()
            async with sessions() as session:
                rows = (
                    await session.execute(
                        select(InventoryItem).order_by(InventoryItem.id.asc())
                    )
                ).scalars().all()
                states = [row.credential_vault_state for row in rows]
                statuses = [row.status for row in rows]

            async with sessions() as session:
                verification = await verify_credential_vault_batch(
                    session,
                    cipher,
                    batch_size=50,
                    apply=True,
                    confirmation=VERIFY_CONFIRMATION,
                )
                await session.commit()
            async with sessions() as session:
                dry_finalize = await finalize_credential_vault_batch(
                    session,
                    cipher,
                    batch_size=50,
                    apply=False,
                )
                await session.rollback()
            async with sessions() as session:
                finalized = await finalize_credential_vault_batch(
                    session,
                    cipher,
                    batch_size=50,
                    apply=True,
                    finalization_enabled=True,
                    confirmation=FINALIZE_CONFIRMATION,
                )
                await session.commit()
            async with sessions() as session:
                encrypted_row = await session.scalar(
                    select(InventoryItem).where(
                        InventoryItem.credential_vault_state == "encrypted"
                    )
                )
                return (
                    backfill,
                    states,
                    statuses,
                    verification,
                    dry_finalize,
                    finalized,
                    encrypted_row,
                )
        finally:
            await engine.dispose()

    (
        backfill,
        states,
        statuses,
        verification,
        dry_finalize,
        finalized,
        encrypted_row,
    ) = asyncio.run(scenario())
    assert backfill.eligible == 1
    assert backfill.duplicates == 1
    assert states == ["encrypted", "quarantined"]
    assert statuses == [ItemStatus.AVAILABLE, ItemStatus.DISABLED]
    assert verification.valid == 1
    assert dry_finalize.eligible == 1
    assert finalized.eligible == 1
    assert encrypted_row.credentials == f"vaulted:{encrypted_row.id}"
    assert encrypted_row.credential_ciphertext is not None
