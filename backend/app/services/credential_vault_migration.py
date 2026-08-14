import hmac
from dataclasses import asdict, dataclass

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import InventoryItem, ItemStatus, utcnow
from app.services.credential_vault import (
    CREDENTIAL_VAULT_ADVISORY_LOCK_ID,
    LEGACY_ERASED_PREFIX,
    MASKED_PREVIEW,
    CredentialCipher,
    CredentialVaultError,
    canonicalize_credential,
    encrypted_credential_values,
    inventory_credential_binding,
)

MAX_VAULT_BATCH_SIZE = 1_000
BACKFILL_CONFIRMATION = "APPLY_CREDENTIAL_VAULT_BACKFILL"
VERIFY_CONFIRMATION = "APPLY_CREDENTIAL_VAULT_VERIFICATION"
FINALIZE_CONFIRMATION = "ERASE_VERIFIED_LEGACY_CREDENTIALS"


class CredentialVaultOperationError(RuntimeError):
    pass


@dataclass
class CredentialVaultCounts:
    total: int
    legacy: int
    encrypted: int
    quarantined: int
    verified: int
    legacy_erased: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class CredentialVaultBatchReport:
    operation: str
    applied: bool
    scanned: int = 0
    eligible: int = 0
    valid: int = 0
    invalid: int = 0
    duplicates: int = 0
    quarantined: int = 0
    skipped: int = 0
    last_id: int = 0
    done: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _validate_batch(after_id: int, batch_size: int) -> None:
    if isinstance(after_id, bool) or after_id < 0:
        raise CredentialVaultOperationError("Vault cursor must be a non-negative integer.")
    if isinstance(batch_size, bool) or not 1 <= batch_size <= MAX_VAULT_BATCH_SIZE:
        raise CredentialVaultOperationError(
            f"Vault batch size must be between 1 and {MAX_VAULT_BATCH_SIZE}."
        )


async def _acquire_vault_lock(db: AsyncSession) -> None:
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"),
        {"lock_id": CREDENTIAL_VAULT_ADVISORY_LOCK_ID},
    )


async def count_credential_vault_rows(db: AsyncSession) -> CredentialVaultCounts:
    row = (
        await db.execute(
            select(
                func.count(InventoryItem.id),
                func.count(InventoryItem.id).filter(
                    InventoryItem.credential_vault_state == "legacy"
                ),
                func.count(InventoryItem.id).filter(
                    InventoryItem.credential_vault_state == "encrypted"
                ),
                func.count(InventoryItem.id).filter(
                    InventoryItem.credential_vault_state == "quarantined"
                ),
                func.count(InventoryItem.id).filter(
                    InventoryItem.credential_vault_verified_at.is_not(None)
                ),
                func.count(InventoryItem.id).filter(
                    InventoryItem.credential_legacy_erased_at.is_not(None)
                ),
            )
        )
    ).one()
    return CredentialVaultCounts(*(int(value or 0) for value in row))


def _clear_envelope(item: InventoryItem) -> None:
    item.credential_ciphertext = None
    item.credential_nonce = None
    item.credential_key_version = None
    item.credential_envelope_version = None
    item.credential_masked_preview = None
    item.credential_canonical_length = None
    item.credential_vault_verified_at = None
    item.credential_legacy_erased_at = None


def _quarantine(
    item: InventoryItem,
    *,
    reason: str,
    fingerprint: bytes | None,
    preserve_envelope: bool = False,
) -> None:
    if preserve_envelope:
        item.credential_vault_verified_at = None
    else:
        _clear_envelope(item)
    item.credential_fingerprint = fingerprint
    item.credential_vault_state = "quarantined"
    item.credential_quarantine_reason = reason
    item.credential_vault_updated_at = utcnow()
    if item.status == ItemStatus.AVAILABLE:
        item.status = ItemStatus.DISABLED


def _apply_envelope(item: InventoryItem, values: dict[str, object]) -> None:
    for field, value in values.items():
        setattr(item, field, value)
    item.credential_vault_updated_at = utcnow()


def _verified_plaintext(item: InventoryItem, cipher: CredentialCipher) -> str:
    plaintext = cipher.decrypt(
        ciphertext=item.credential_ciphertext,
        nonce=item.credential_nonce,
        key_version=item.credential_key_version,
        fingerprint=item.credential_fingerprint,
        envelope_version=item.credential_envelope_version,
        binding=inventory_credential_binding(item.id),
    )
    if item.credential_canonical_length != len(plaintext.encode("utf-8")):
        raise CredentialVaultError("Credential length metadata is invalid.")
    if item.credential_masked_preview != MASKED_PREVIEW:
        raise CredentialVaultError("Credential preview metadata is invalid.")
    if item.credential_legacy_erased_at is None:
        legacy = canonicalize_credential(item.credentials)
        if not hmac.compare_digest(legacy.encode("utf-8"), plaintext.encode("utf-8")):
            raise CredentialVaultError("Credential envelope does not match the legacy row.")
    elif item.credentials != f"{LEGACY_ERASED_PREFIX}{item.id}":
        raise CredentialVaultError("Credential legacy tombstone is invalid.")
    return plaintext


async def backfill_credential_vault_batch(
    db: AsyncSession,
    cipher: CredentialCipher,
    *,
    after_id: int = 0,
    batch_size: int = 250,
    apply: bool = False,
    confirmation: str = "",
    known_fingerprints: set[bytes] | None = None,
) -> CredentialVaultBatchReport:
    _validate_batch(after_id, batch_size)
    if apply and confirmation != BACKFILL_CONFIRMATION:
        raise CredentialVaultOperationError("Backfill confirmation is invalid.")
    if apply:
        await _acquire_vault_lock(db)

    statement = (
        select(InventoryItem)
        .where(
            InventoryItem.id > after_id,
            InventoryItem.credential_vault_state == "legacy",
            InventoryItem.credential_legacy_erased_at.is_(None),
        )
        .order_by(InventoryItem.id.asc())
        .limit(batch_size)
    )
    if apply:
        statement = statement.with_for_update()
    rows = (await db.execute(statement)).scalars().all()
    report = CredentialVaultBatchReport(
        operation="backfill",
        applied=apply,
        scanned=len(rows),
        last_id=int(rows[-1].id) if rows else after_id,
        done=len(rows) < batch_size,
    )
    if not rows:
        return report

    candidates: list[tuple[InventoryItem, bytes]] = []
    for item in rows:
        try:
            fingerprint = cipher.fingerprint(item.credentials)
        except CredentialVaultError:
            report.invalid += 1
            report.quarantined += 1
            if apply:
                _quarantine(item, reason="invalid_legacy_value", fingerprint=None)
            continue
        candidates.append((item, fingerprint))

    candidate_fingerprints = [fingerprint for _, fingerprint in candidates]
    existing_fingerprints: set[bytes] = set()
    if candidate_fingerprints:
        existing_result = await db.execute(
            select(InventoryItem.credential_fingerprint).where(
                InventoryItem.credential_vault_state == "encrypted",
                InventoryItem.credential_fingerprint.in_(candidate_fingerprints),
            )
        )
        existing_fingerprints = set(existing_result.scalars().all())

    seen = known_fingerprints if known_fingerprints is not None else set()
    accepted_in_batch: set[bytes] = set()
    for item, fingerprint in candidates:
        if (
            fingerprint in existing_fingerprints
            or fingerprint in accepted_in_batch
            or fingerprint in seen
        ):
            report.duplicates += 1
            report.quarantined += 1
            if apply:
                _quarantine(
                    item,
                    reason="duplicate_fingerprint",
                    fingerprint=fingerprint,
                )
            continue
        accepted_in_batch.add(fingerprint)
        seen.add(fingerprint)
        report.eligible += 1
        if apply:
            envelope = cipher.encrypt(
                item.credentials,
                binding=inventory_credential_binding(item.id),
            )
            _apply_envelope(item, encrypted_credential_values(envelope))

    if apply:
        await db.flush()
    return report


async def verify_credential_vault_batch(
    db: AsyncSession,
    cipher: CredentialCipher,
    *,
    after_id: int = 0,
    batch_size: int = 250,
    apply: bool = False,
    confirmation: str = "",
) -> CredentialVaultBatchReport:
    _validate_batch(after_id, batch_size)
    if apply and confirmation != VERIFY_CONFIRMATION:
        raise CredentialVaultOperationError("Verification confirmation is invalid.")
    if apply:
        await _acquire_vault_lock(db)
    statement = (
        select(InventoryItem)
        .where(
            InventoryItem.id > after_id,
            InventoryItem.credential_vault_state == "encrypted",
        )
        .order_by(InventoryItem.id.asc())
        .limit(batch_size)
    )
    if apply:
        statement = statement.with_for_update()
    rows = (await db.execute(statement)).scalars().all()
    report = CredentialVaultBatchReport(
        operation="verify",
        applied=apply,
        scanned=len(rows),
        last_id=int(rows[-1].id) if rows else after_id,
        done=len(rows) < batch_size,
    )
    for item in rows:
        try:
            _verified_plaintext(item, cipher)
        except CredentialVaultError:
            report.invalid += 1
            report.quarantined += 1
            if apply:
                _quarantine(
                    item,
                    reason="integrity_verification_failed",
                    fingerprint=item.credential_fingerprint,
                    preserve_envelope=True,
                )
            continue
        report.valid += 1
        report.eligible += 1
        if apply:
            item.credential_vault_verified_at = utcnow()
    if apply:
        await db.flush()
    return report


async def finalize_credential_vault_batch(
    db: AsyncSession,
    cipher: CredentialCipher,
    *,
    after_id: int = 0,
    batch_size: int = 250,
    apply: bool = False,
    finalization_enabled: bool = False,
    confirmation: str = "",
) -> CredentialVaultBatchReport:
    _validate_batch(after_id, batch_size)
    if apply and (
        not finalization_enabled or confirmation != FINALIZE_CONFIRMATION
    ):
        raise CredentialVaultOperationError("Finalization gate or confirmation is invalid.")
    if apply:
        await _acquire_vault_lock(db)
    statement = (
        select(InventoryItem)
        .where(
            InventoryItem.id > after_id,
            InventoryItem.credential_vault_state == "encrypted",
            InventoryItem.credential_vault_verified_at.is_not(None),
            InventoryItem.credential_legacy_erased_at.is_(None),
            InventoryItem.credential_vault_updated_at.is_not(None),
            InventoryItem.credential_vault_verified_at
            >= InventoryItem.credential_vault_updated_at,
        )
        .order_by(InventoryItem.id.asc())
        .limit(batch_size)
    )
    if apply:
        statement = statement.with_for_update()
    rows = (await db.execute(statement)).scalars().all()
    report = CredentialVaultBatchReport(
        operation="finalize",
        applied=apply,
        scanned=len(rows),
        last_id=int(rows[-1].id) if rows else after_id,
        done=len(rows) < batch_size,
    )
    for item in rows:
        try:
            _verified_plaintext(item, cipher)
        except CredentialVaultError:
            report.invalid += 1
            continue
        report.valid += 1
        report.eligible += 1
        if apply:
            item.credentials = f"{LEGACY_ERASED_PREFIX}{item.id}"
            item.credential_legacy_erased_at = utcnow()
    if apply:
        await db.flush()
    return report
