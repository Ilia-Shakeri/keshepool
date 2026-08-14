import asyncio
import importlib.util
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models import InventoryItem, ItemStatus, utcnow
from app.services import catalog_service
from app.services.credential_vault import (
    CredentialCipher,
    CredentialVaultError,
    encrypted_credential_values,
    inventory_credential_binding,
)
from app.services.credential_vault_migration import (
    BACKFILL_CONFIRMATION,
    FINALIZE_CONFIRMATION,
    VERIFY_CONFIRMATION,
    CredentialVaultOperationError,
    backfill_credential_vault_batch,
    finalize_credential_vault_batch,
    verify_credential_vault_batch,
)


class _MemoryKeys:
    active_version = "v1"

    def encryption_key(self, version: str) -> bytes:
        if version != "v1":
            raise CredentialVaultError("Unknown test key.")
        return b"E" * 32

    def fingerprint_key(self) -> bytes:
        return b"F" * 32


def _cipher() -> CredentialCipher:
    return CredentialCipher(_MemoryKeys(), nonce_factory=lambda size: b"N" * size)


class _ScalarRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def scalars(self):
        return _ScalarRows(self.rows)

    def all(self):
        return self.rows


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.executed = 0
        self.flushed = 0
        self.calls = []

    async def execute(self, statement, parameters=None):
        self.executed += 1
        self.calls.append((statement, parameters))
        if self.responses:
            return self.responses.pop(0)
        return _Result()

    async def flush(self):
        self.flushed += 1


def _legacy_item(item_id: int, value: str) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        product_id="product",
        variant_id="variant",
        credentials=value,
        credential_vault_state="legacy",
        status=ItemStatus.AVAILABLE,
    )


def test_backfill_is_stable_and_quarantines_global_duplicates() -> None:
    first = _legacy_item(1, "same-value")
    duplicate = _legacy_item(2, "same-value")
    session = _Session([_Result(), _Result([first, duplicate]), _Result()])

    report = asyncio.run(
        backfill_credential_vault_batch(
            session,
            _cipher(),
            apply=True,
            confirmation=BACKFILL_CONFIRMATION,
        )
    )

    assert report.scanned == 2
    assert report.eligible == 1
    assert report.duplicates == 1
    assert report.quarantined == 1
    assert report.last_id == 2
    assert first.credential_vault_state == "encrypted"
    assert first.credential_ciphertext is not None
    assert duplicate.credential_vault_state == "quarantined"
    assert duplicate.credential_quarantine_reason == "duplicate_fingerprint"
    assert duplicate.status == ItemStatus.DISABLED
    assert session.flushed == 1
    assert "same-value" not in repr(report.to_dict())


def test_dry_run_never_mutates_legacy_rows() -> None:
    item = _legacy_item(4, "dry-run-value")
    session = _Session([_Result([item]), _Result()])
    report = asyncio.run(
        backfill_credential_vault_batch(session, _cipher(), apply=False)
    )
    assert report.eligible == 1
    assert item.credential_vault_state == "legacy"
    assert item.credential_ciphertext is None
    assert session.flushed == 0


def test_catalog_dual_write_binds_ciphertext_to_inserted_inventory_id(monkeypatch) -> None:
    cipher = _cipher()
    session = _Session(
        [
            _Result(),
            _Result(),
            _Result([SimpleNamespace(id=42, credentials="same-value")]),
            _Result(),
        ]
    )
    monkeypatch.setattr(
        catalog_service.settings,
        "CREDENTIAL_VAULT_DUAL_WRITE_ENABLED",
        True,
    )
    monkeypatch.setattr(
        catalog_service,
        "credential_cipher_from_settings",
        lambda config: cipher,
    )

    inserted, duplicates = asyncio.run(
        catalog_service._insert_inventory_rows(
            session,
            "product",
            (("variant-a", "same-value"), ("variant-b", "same-value")),
        )
    )

    assert inserted == 1
    assert duplicates == 1
    update_parameters = session.calls[-1][1]
    assert isinstance(update_parameters, list)
    assert "same-value" not in repr(update_parameters)
    values = update_parameters[0]
    assert cipher.decrypt(
        ciphertext=values["credential_ciphertext"],
        nonce=values["credential_nonce"],
        key_version=values["credential_key_version"],
        fingerprint=values["credential_fingerprint"],
        envelope_version=values["credential_envelope_version"],
        binding=inventory_credential_binding(42),
    ) == "same-value"


def test_verify_then_explicit_finalize_rechecks_and_erases_only_legacy_column() -> None:
    item = _legacy_item(9, "verified-value")
    cipher = _cipher()
    envelope = cipher.encrypt(
        item.credentials,
        binding=inventory_credential_binding(item.id),
    )
    for field, value in encrypted_credential_values(envelope).items():
        setattr(item, field, value)
    item.credential_vault_updated_at = utcnow() - timedelta(minutes=1)

    verify_session = _Session([_Result(), _Result([item])])
    verify_report = asyncio.run(
        verify_credential_vault_batch(
            verify_session,
            cipher,
            apply=True,
            confirmation=VERIFY_CONFIRMATION,
        )
    )
    assert verify_report.valid == 1
    assert item.credential_vault_verified_at is not None

    finalize_session = _Session([_Result(), _Result([item])])
    finalize_report = asyncio.run(
        finalize_credential_vault_batch(
            finalize_session,
            cipher,
            apply=True,
            finalization_enabled=True,
            confirmation=FINALIZE_CONFIRMATION,
        )
    )
    assert finalize_report.valid == 1
    assert item.credentials == "vaulted:9"
    assert item.credential_legacy_erased_at is not None
    assert cipher.decrypt(
        ciphertext=item.credential_ciphertext,
        nonce=item.credential_nonce,
        key_version=item.credential_key_version,
        fingerprint=item.credential_fingerprint,
        envelope_version=item.credential_envelope_version,
        binding=inventory_credential_binding(item.id),
    ) == "verified-value"


def test_finalize_apply_needs_both_runtime_gate_and_exact_confirmation() -> None:
    with pytest.raises(CredentialVaultOperationError):
        asyncio.run(
            finalize_credential_vault_batch(
                _Session([]),
                _cipher(),
                apply=True,
                finalization_enabled=False,
                confirmation=FINALIZE_CONFIRMATION,
            )
        )


def test_failed_verification_quarantines_without_destroying_finalized_envelope() -> None:
    item = _legacy_item(12, "original-value")
    cipher = _cipher()
    envelope = cipher.encrypt(
        item.credentials,
        binding=inventory_credential_binding(item.id),
    )
    for field, value in encrypted_credential_values(envelope).items():
        setattr(item, field, value)
    item.credential_vault_updated_at = utcnow() - timedelta(minutes=2)
    item.credential_vault_verified_at = utcnow() - timedelta(minutes=1)
    item.credential_legacy_erased_at = utcnow()
    item.credentials = "vaulted:12"
    tampered = bytearray(item.credential_ciphertext)
    tampered[0] ^= 1
    item.credential_ciphertext = bytes(tampered)
    preserved_ciphertext = item.credential_ciphertext

    session = _Session([_Result(), _Result([item])])
    report = asyncio.run(
        verify_credential_vault_batch(
            session,
            cipher,
            apply=True,
            confirmation=VERIFY_CONFIRMATION,
        )
    )

    assert report.invalid == 1
    assert item.credential_vault_state == "quarantined"
    assert item.credential_ciphertext == preserved_ciphertext
    assert item.credential_legacy_erased_at is not None
    assert item.credential_vault_verified_at is None


def test_revision_012_is_additive_and_matches_the_model() -> None:
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "012_inventory_credential_vault.py"
    )
    spec = importlib.util.spec_from_file_location("migration_012", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    assert migration.revision == "012"
    assert migration.down_revision == "011"
    source = migration_path.read_text(encoding="utf-8")
    assert 'drop_column("inventory_items", "credentials")' not in source
    assert "UPDATE inventory_items" not in source
    assert "uq_inventory_credential_fingerprint" in source
    assert "credential_envelope_version = 1" in source

    constraints = {item.name for item in InventoryItem.__table__.constraints}
    indexes = {item.name for item in InventoryItem.__table__.indexes}
    assert {
        "ck_inventory_credential_vault_state",
        "ck_inventory_credential_fingerprint_length",
        "ck_inventory_credential_encrypted_bundle",
        "ck_inventory_credential_quarantine_reason",
        "ck_inventory_credential_quarantine_reason_value",
        "ck_inventory_credential_verified_state",
        "ck_inventory_credential_legacy_erasure",
        "ck_inventory_credential_legacy_tombstone",
    } <= constraints
    assert "uq_inventory_credential_fingerprint" in indexes
