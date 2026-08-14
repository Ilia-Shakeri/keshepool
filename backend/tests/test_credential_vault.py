import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.credential_vault import (
    CredentialCipher,
    CredentialIntegrityError,
    CredentialUnavailableError,
    CredentialVaultError,
    FileCredentialKeyProvider,
    canonicalize_credential,
    decrypt_inventory_credential,
    encrypted_credential_values,
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


def test_canonicalization_is_conservative_and_bounded() -> None:
    assert canonicalize_credential("  Cafe\u0301\r\nline  ") == "Café\nline"
    with pytest.raises(CredentialVaultError):
        canonicalize_credential("   ")
    with pytest.raises(CredentialVaultError):
        canonicalize_credential("x" * 4097)


def test_envelope_round_trip_and_blind_fingerprint() -> None:
    cipher = _cipher()
    envelope = cipher.encrypt("sample-account\r\nline", binding="inventory-item:7")
    assert envelope.key_version == "v1"
    assert len(envelope.fingerprint) == 32
    assert b"sample-account" not in envelope.ciphertext
    assert envelope.masked_preview == "••••••••"
    assert cipher.decrypt(
        ciphertext=envelope.ciphertext,
        nonce=envelope.nonce,
        key_version=envelope.key_version,
        fingerprint=envelope.fingerprint,
        envelope_version=envelope.envelope_version,
        binding="inventory-item:7",
    ) == "sample-account\nline"


def test_equivalent_input_has_one_fingerprint_but_random_nonce_can_vary() -> None:
    cipher = _cipher()
    first = cipher.encrypt(" value\r\n", binding="inventory-item:7")
    second = cipher.encrypt("value\n", binding="inventory-item:8")
    assert first.fingerprint == second.fingerprint


def test_ciphertext_or_metadata_tamper_fails_closed() -> None:
    cipher = _cipher()
    envelope = cipher.encrypt("sample-value", binding="inventory-item:7")
    changed = bytearray(envelope.ciphertext)
    changed[0] ^= 1
    with pytest.raises(CredentialIntegrityError):
        cipher.decrypt(
            ciphertext=bytes(changed),
            nonce=envelope.nonce,
            key_version=envelope.key_version,
            fingerprint=envelope.fingerprint,
            envelope_version=envelope.envelope_version,
            binding="inventory-item:7",
        )
    with pytest.raises(CredentialIntegrityError):
        cipher.decrypt(
            ciphertext=envelope.ciphertext,
            nonce=envelope.nonce,
            key_version=envelope.key_version,
            fingerprint=b"X" * 32,
            envelope_version=envelope.envelope_version,
            binding="inventory-item:7",
        )
    with pytest.raises(CredentialIntegrityError):
        cipher.decrypt(
            ciphertext=envelope.ciphertext,
            nonce=envelope.nonce,
            key_version=envelope.key_version,
            fingerprint=envelope.fingerprint,
            envelope_version=envelope.envelope_version,
            binding="inventory-item:8",
        )


def test_envelope_values_and_read_preference_never_export_plaintext() -> None:
    cipher = _cipher()
    envelope = cipher.encrypt("sample-value", binding="inventory-item:7")
    values = encrypted_credential_values(envelope)
    assert "sample-value" not in repr(values)
    item = SimpleNamespace(
        id=7,
        credentials="sample-value",
        **values,
    )
    encrypted_config = SimpleNamespace(
        CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED=True,
        CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED=True,
    )
    assert decrypt_inventory_credential(item, encrypted_config, cipher=cipher) == "sample-value"

    item.credential_vault_state = "quarantined"
    with pytest.raises(CredentialUnavailableError):
        decrypt_inventory_credential(item, encrypted_config, cipher=cipher)


def test_file_provider_loads_only_bounded_absolute_key_files(tmp_path: Path) -> None:
    encryption_path = tmp_path / "encryption.json"
    fingerprint_path = tmp_path / "fingerprint.json"
    encryption_path.write_text(
        json.dumps(
            {
                "activeVersion": "v2",
                "keys": {"v1": base64.b64encode(b"1" * 32).decode(), "v2": base64.b64encode(b"2" * 32).decode()},
            }
        ),
        encoding="utf-8",
    )
    fingerprint_path.write_text(
        json.dumps({"key": base64.b64encode(b"3" * 32).decode()}),
        encoding="utf-8",
    )

    provider = FileCredentialKeyProvider(str(encryption_path), str(fingerprint_path))
    assert provider.active_version == "v2"
    assert provider.encryption_key("v2") == b"2" * 32
    assert provider.fingerprint_key() == b"3" * 32

    with pytest.raises(CredentialVaultError):
        FileCredentialKeyProvider("relative.json", str(fingerprint_path))

    fingerprint_path.write_text(
        json.dumps({"key": base64.b64encode(b"2" * 32).decode()}),
        encoding="utf-8",
    )
    with pytest.raises(CredentialVaultError, match="fingerprint key must be separate"):
        FileCredentialKeyProvider(str(encryption_path), str(fingerprint_path))


def _settings_values(**overrides):
    values = {
        "ENVIRONMENT": "test",
        "DATABASE_URL": "postgresql+asyncpg://user:password@db/test",
        "BOT_TOKEN": "123456:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "ADMIN_BOT_TOKEN": "123457:BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        "TELEGRAM_BOT_MODE": "disabled",
        "WEBHOOK_URL": "https://example.test",
        "MAIN_TELEGRAM_WEBHOOK_SECRET": "test-main-webhook-secret",
        "ADMIN_TELEGRAM_WEBHOOK_SECRET": "test-admin-webhook-secret",
        "WEB_APP_URL": "https://example.test",
        "ADMIN_TELEGRAM_IDS": "123456",
        "USDT_TO_IRR_RATE": 85000,
    }
    values.update(overrides)
    return values


def test_vault_rollout_flags_default_off_and_paths_fail_closed() -> None:
    configured = Settings(**_settings_values())
    assert configured.CREDENTIAL_VAULT_DUAL_WRITE_ENABLED is False
    assert configured.CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED is False
    assert configured.CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED is True
    assert configured.CREDENTIAL_VAULT_FINALIZE_ENABLED is False

    with pytest.raises(ValidationError, match="absolute mounted secret path"):
        Settings(
            **_settings_values(
                CREDENTIAL_VAULT_DUAL_WRITE_ENABLED=True,
                CREDENTIAL_VAULT_ENCRYPTION_KEYS_FILE="relative.json",
                CREDENTIAL_VAULT_FINGERPRINT_KEY_FILE="relative.json",
            )
        )


def test_vault_finalization_requires_completed_read_cutover() -> None:
    key_dir = Path.cwd().resolve()
    with pytest.raises(ValidationError, match="finalization requires"):
        Settings(
            **_settings_values(
                CREDENTIAL_VAULT_FINALIZE_ENABLED=True,
                CREDENTIAL_VAULT_ENCRYPTION_KEYS_FILE=str(key_dir / "encryption.json"),
                CREDENTIAL_VAULT_FINGERPRINT_KEY_FILE=str(key_dir / "fingerprint.json"),
            )
        )
