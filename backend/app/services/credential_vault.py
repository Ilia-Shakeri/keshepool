import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


MAX_CREDENTIAL_CHARACTERS = 4096
MAX_CREDENTIAL_BYTES = 16_384
MAX_KEY_FILE_BYTES = 32_768
NONCE_BYTES = 12
FINGERPRINT_BYTES = 32
ENVELOPE_VERSION = 1
MAX_BINDING_BYTES = 256
CREDENTIAL_VAULT_ADVISORY_LOCK_ID = 4_830_292_155_821_271_044
MASKED_PREVIEW = "\u2022" * 8
LEGACY_ERASED_PREFIX = "vaulted:"
_KEY_VERSION = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
_AAD_PREFIX = b"keshepool:inventory-credential:v1:"


class CredentialVaultError(ValueError):
    pass


class CredentialIntegrityError(CredentialVaultError):
    pass


class CredentialUnavailableError(CredentialVaultError):
    pass


class CredentialKeyProvider(Protocol):
    @property
    def active_version(self) -> str: ...

    def encryption_key(self, version: str) -> bytes: ...

    def fingerprint_key(self) -> bytes: ...


@dataclass(frozen=True)
class EncryptedCredential:
    ciphertext: bytes
    nonce: bytes
    key_version: str
    envelope_version: int
    fingerprint: bytes
    masked_preview: str
    canonical_length: int


def canonicalize_credential(value: str) -> str:
    if not isinstance(value, str):
        raise CredentialVaultError("Credential must be text.")
    canonical = unicodedata.normalize("NFC", value.replace("\r\n", "\n").replace("\r", "\n")).strip()
    encoded = canonical.encode("utf-8")
    if not canonical:
        raise CredentialVaultError("Credential cannot be empty.")
    if len(canonical) > MAX_CREDENTIAL_CHARACTERS or len(encoded) > MAX_CREDENTIAL_BYTES:
        raise CredentialVaultError("Credential is too large.")
    return canonical


def _decode_key(raw_value: object) -> bytes:
    if not isinstance(raw_value, str):
        raise CredentialVaultError("Vault key file is invalid.")
    try:
        decoded = base64.b64decode(raw_value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise CredentialVaultError("Vault key file is invalid.") from exc
    if len(decoded) != 32:
        raise CredentialVaultError("Vault keys must be 32 bytes.")
    return decoded


def _load_json_file(path: Path) -> dict[str, object]:
    if not path.is_absolute() or not path.is_file():
        raise CredentialVaultError("Vault key file is unavailable.")
    if path.stat().st_size > MAX_KEY_FILE_BYTES:
        raise CredentialVaultError("Vault key file is too large.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CredentialVaultError("Vault key file is invalid.") from exc
    if not isinstance(payload, dict):
        raise CredentialVaultError("Vault key file is invalid.")
    return payload


class FileCredentialKeyProvider:
    def __init__(self, encryption_keys_path: str, fingerprint_key_path: str):
        encryption_path = Path(encryption_keys_path)
        fingerprint_path = Path(fingerprint_key_path)
        try:
            if encryption_path.resolve(strict=True) == fingerprint_path.resolve(strict=True):
                raise CredentialVaultError("Vault key files must be separate.")
        except OSError as exc:
            raise CredentialVaultError("Vault key file is unavailable.") from exc
        encryption_payload = _load_json_file(encryption_path)
        active_version = encryption_payload.get("activeVersion")
        raw_keys = encryption_payload.get("keys")
        if (
            not isinstance(active_version, str)
            or not _KEY_VERSION.fullmatch(active_version)
            or not isinstance(raw_keys, dict)
            or active_version not in raw_keys
        ):
            raise CredentialVaultError("Vault encryption key file is invalid.")
        keys: dict[str, bytes] = {}
        for version, raw_key in raw_keys.items():
            if not isinstance(version, str) or not _KEY_VERSION.fullmatch(version):
                raise CredentialVaultError("Vault encryption key version is invalid.")
            keys[version] = _decode_key(raw_key)
        if len(set(keys.values())) != len(keys):
            raise CredentialVaultError("Vault encryption key versions must be distinct.")
        fingerprint_payload = _load_json_file(fingerprint_path)
        self._active_version = active_version
        self._keys = keys
        self._fingerprint_key = _decode_key(fingerprint_payload.get("key"))
        if any(
            hmac.compare_digest(self._fingerprint_key, encryption_key)
            for encryption_key in self._keys.values()
        ):
            raise CredentialVaultError("Vault fingerprint key must be separate.")

    @property
    def active_version(self) -> str:
        return self._active_version

    def encryption_key(self, version: str) -> bytes:
        try:
            return self._keys[version]
        except KeyError as exc:
            raise CredentialVaultError("Vault encryption key version is unavailable.") from exc

    def fingerprint_key(self) -> bytes:
        return self._fingerprint_key


class CredentialCipher:
    def __init__(
        self,
        key_provider: CredentialKeyProvider,
        *,
        nonce_factory: Callable[[int], bytes] = os.urandom,
    ):
        self._keys = key_provider
        self._nonce_factory = nonce_factory

    def fingerprint(self, value: str) -> bytes:
        canonical = canonicalize_credential(value).encode("utf-8")
        return hmac.new(
            self._keys.fingerprint_key(),
            canonical,
            hashlib.sha256,
        ).digest()

    @staticmethod
    def _aad(key_version: str, fingerprint: bytes, binding: str) -> bytes:
        if not _KEY_VERSION.fullmatch(key_version) or len(fingerprint) != FINGERPRINT_BYTES:
            raise CredentialVaultError("Encrypted credential metadata is invalid.")
        if not isinstance(binding, str):
            raise CredentialVaultError("Credential binding is invalid.")
        encoded_binding = binding.encode("utf-8")
        if not encoded_binding or len(encoded_binding) > MAX_BINDING_BYTES:
            raise CredentialVaultError("Credential binding is invalid.")
        return (
            _AAD_PREFIX
            + len(encoded_binding).to_bytes(2, "big")
            + encoded_binding
            + key_version.encode("ascii")
            + fingerprint
        )

    def encrypt(self, value: str, *, binding: str) -> EncryptedCredential:
        canonical = canonicalize_credential(value)
        plaintext = canonical.encode("utf-8")
        key_version = self._keys.active_version
        fingerprint = self.fingerprint(canonical)
        nonce = self._nonce_factory(NONCE_BYTES)
        if len(nonce) != NONCE_BYTES:
            raise CredentialVaultError("Vault nonce source is invalid.")
        ciphertext = AESGCM(self._keys.encryption_key(key_version)).encrypt(
            nonce,
            plaintext,
            self._aad(key_version, fingerprint, binding),
        )
        return EncryptedCredential(
            ciphertext=ciphertext,
            nonce=nonce,
            key_version=key_version,
            envelope_version=ENVELOPE_VERSION,
            fingerprint=fingerprint,
            masked_preview=MASKED_PREVIEW,
            canonical_length=len(plaintext),
        )

    def decrypt(
        self,
        *,
        ciphertext: bytes | None,
        nonce: bytes | None,
        key_version: str | None,
        fingerprint: bytes | None,
        envelope_version: int | None,
        binding: str,
    ) -> str:
        if (
            not isinstance(ciphertext, bytes)
            or not ciphertext
            or not isinstance(nonce, bytes)
            or len(nonce) != NONCE_BYTES
            or not isinstance(key_version, str)
            or not isinstance(fingerprint, bytes)
            or envelope_version != ENVELOPE_VERSION
        ):
            raise CredentialIntegrityError("Encrypted credential is invalid.")
        try:
            plaintext = AESGCM(self._keys.encryption_key(key_version)).decrypt(
                nonce,
                ciphertext,
                self._aad(key_version, fingerprint, binding),
            )
            value = plaintext.decode("utf-8")
        except (CredentialVaultError, InvalidTag, UnicodeError, ValueError) as exc:
            raise CredentialIntegrityError("Encrypted credential integrity check failed.") from exc
        canonical = canonicalize_credential(value)
        expected = self.fingerprint(canonical)
        if not hmac.compare_digest(expected, fingerprint):
            raise CredentialIntegrityError("Encrypted credential fingerprint check failed.")
        return canonical


def credential_cipher_from_settings(config: Any) -> CredentialCipher:
    return CredentialCipher(
        FileCredentialKeyProvider(
            str(config.CREDENTIAL_VAULT_ENCRYPTION_KEYS_FILE).strip(),
            str(config.CREDENTIAL_VAULT_FINGERPRINT_KEY_FILE).strip(),
        )
    )


def encrypted_credential_values(envelope: EncryptedCredential) -> dict[str, object]:
    return {
        "credential_ciphertext": envelope.ciphertext,
        "credential_nonce": envelope.nonce,
        "credential_key_version": envelope.key_version,
        "credential_envelope_version": envelope.envelope_version,
        "credential_fingerprint": envelope.fingerprint,
        "credential_masked_preview": envelope.masked_preview,
        "credential_canonical_length": envelope.canonical_length,
        "credential_vault_state": "encrypted",
        "credential_quarantine_reason": None,
        "credential_vault_verified_at": None,
        "credential_legacy_erased_at": None,
    }


def decrypt_inventory_credential(
    item: Any,
    config: Any,
    *,
    cipher: CredentialCipher | None = None,
) -> str:
    state = getattr(item, "credential_vault_state", "legacy") or "legacy"
    legacy_erased = getattr(item, "credential_legacy_erased_at", None) is not None

    if state == "quarantined":
        raise CredentialUnavailableError("Credential is quarantined.")

    if config.CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED and state == "encrypted":
        active_cipher = cipher or credential_cipher_from_settings(config)
        return active_cipher.decrypt(
            ciphertext=getattr(item, "credential_ciphertext", None),
            nonce=getattr(item, "credential_nonce", None),
            key_version=getattr(item, "credential_key_version", None),
            fingerprint=getattr(item, "credential_fingerprint", None),
            envelope_version=getattr(item, "credential_envelope_version", None),
            binding=inventory_credential_binding(getattr(item, "id", None)),
        )

    legacy_value = getattr(item, "credentials", None)
    if (
        config.CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED
        and not legacy_erased
        and isinstance(legacy_value, str)
        and legacy_value
    ):
        return legacy_value

    if state == "encrypted" and config.CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED:
        raise CredentialIntegrityError("Encrypted credential metadata is unavailable.")
    raise CredentialUnavailableError("Credential is unavailable.")


def inventory_credential_binding(item_id: Any) -> str:
    if not isinstance(item_id, int) or isinstance(item_id, bool) or item_id <= 0:
        raise CredentialVaultError("Inventory credential binding is invalid.")
    return f"inventory-item:{item_id}"
