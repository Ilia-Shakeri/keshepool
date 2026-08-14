# Inventory credential vault rollout

Revision `012` expands `inventory_items` with an authenticated encrypted envelope while keeping the existing `credentials` column. The migration does not read, rewrite, null, or drop that column. All runtime gates default to the legacy path so the schema can ship before any key or data operation.

## Envelope and state rules

Each encrypted row stores ciphertext, a 12-byte nonce, key version, envelope version, a keyed 32-byte fingerprint, a fixed masked preview, and the canonical byte length. Authenticated data binds the envelope to the stable inventory item ID. Moving an envelope to another row therefore fails verification. The database permits one encrypted row per global fingerprint and rejects partial encrypted envelopes.

The state is one of:

- `legacy`: the old value remains the active source.
- `encrypted`: a complete envelope exists. The old value remains until the separate finalization command runs.
- `quarantined`: the value was invalid, duplicated, or failed integrity verification. Available stock is disabled when the migration tool applies quarantine.

Canonicalization is deliberately narrow: Unicode NFC, CRLF or CR to LF, and outer whitespace removal. Values are limited to 4,096 characters and 16,384 UTF-8 bytes. The fingerprint uses a separate key and is never a plain digest. Reports contain counts and numeric cursors only.

## Key files

Keep both files outside the repository and mount them read-only into the backend and worker only. Each encoded key must decode to exactly 32 random bytes. The encryption file retains old versions needed for reads and names one active write version:

```json
{"activeVersion":"v1","keys":{"v1":"<base64-encoded-32-byte-key>"}}
```

The fingerprint file has a separate key:

```json
{"key":"<base64-encoded-32-byte-key>"}
```

Set the two configuration paths to absolute container paths. Never commit, print, send, or place these files in a source export. Back them up through the reviewed secret-management process separately from database backups. Losing an old encryption key makes rows under that version unreadable. Changing the fingerprint key without a planned full migration breaks duplicate detection.

## Gates

```env
CREDENTIAL_VAULT_DUAL_WRITE_ENABLED=false
CREDENTIAL_VAULT_READ_PREFER_ENCRYPTED=false
CREDENTIAL_VAULT_LEGACY_FALLBACK_ENABLED=true
CREDENTIAL_VAULT_FINALIZE_ENABLED=false
CREDENTIAL_VAULT_ENCRYPTION_KEYS_FILE=/run/secrets/keshepool-credential-encryption.json
CREDENTIAL_VAULT_FINGERPRINT_KEY_FILE=/run/secrets/keshepool-credential-fingerprint.json
```

Enabling dual writes or encrypted reads requires both absolute paths. Finalization additionally requires dual writes and encrypted reads to be enabled and legacy fallback to be disabled. The process still needs the explicit finalization command and exact confirmation phrase.

## Staged procedure

Use a maintenance-approved database target. Do not test this process with customer values or a live database. Capture and verify a restorable encrypted database backup before any applied data step.

1. Deploy revision `012` with every vault write, read, and finalization gate at its default. Run the count command; it does not load keys or credential values.

   ```sh
   python scripts/manage_credential_vault.py count
   ```

2. Mount the two key files. Enable dual writes only. Prove on a disposable database that a new import writes a complete envelope and that a duplicate fingerprint is rejected. Keep encrypted reads off during this expand step.

3. Start a complete dry run from ID zero. One batch runs by default. Use the returned `next_after_id` as the next cursor, or set a reviewed `--max-batches` limit. For an exact dry-run duplicate inventory, start at zero and keep the same uninterrupted command so fingerprints found in earlier batches remain in memory.

   ```sh
   python scripts/manage_credential_vault.py backfill --batch-size 250 --max-batches 10000
   ```

4. Review invalid and duplicate counts. Applied backfill is resumable by stable primary key and serializes against encrypted imports. It never erases the old column. The exact confirmation is mandatory.

   ```sh
   python scripts/manage_credential_vault.py backfill --batch-size 250 --max-batches 10000 --apply --confirm APPLY_CREDENTIAL_VAULT_BACKFILL
   ```

5. Run integrity verification first in dry-run mode, then apply verification marks. Verification decrypts only in process memory, checks the row binding, fingerprint, metadata, and equality with the canonical legacy value, and emits no value.

   ```sh
   python scripts/manage_credential_vault.py verify --batch-size 250 --max-batches 10000
   python scripts/manage_credential_vault.py verify --batch-size 250 --max-batches 10000 --apply --confirm APPLY_CREDENTIAL_VAULT_VERIFICATION
   ```

6. Fix or retire quarantined rows through a separately reviewed operator procedure. Repeat count and verification until the reviewed acceptance threshold is met. Do not mark a quarantined row `legacy` without resolving the underlying duplicate or invalid value.

7. Enable encrypted-read preference while legacy fallback stays enabled. Test purchase and owner-only reveal flows on disposable data and every supported client. Then disable legacy fallback in a separate reviewed release and repeat the tests. Rollback before finalization is to re-enable legacy fallback and disable encrypted read preference.

8. Keep plaintext finalization off until encrypted-only reads have run through the full observation window, old key recovery is proven, and a restore drill passes. The dry run rechecks every candidate and does not alter data.

   ```sh
   python scripts/manage_credential_vault.py finalize --batch-size 250 --max-batches 10000
   ```

9. For the irreversible step, set `CREDENTIAL_VAULT_FINALIZE_ENABLED=true` and run the explicit applied command. It replaces only the verified legacy column with a row-specific tombstone. It does not delete the encrypted envelope. There is no automatic finalization path.

   ```sh
   python scripts/manage_credential_vault.py finalize --batch-size 250 --max-batches 10000 --apply --confirm ERASE_VERIFIED_LEGACY_CREDENTIALS
   ```

After any finalized row exists, a binary that reads only the legacy column is not a safe rollback target. Restore service with an envelope-aware binary and the required old encryption keys. Database downgrade is not a credential recovery method.

## Operational limits

- Run one applied backfill, verification, or finalization process at a time. A database advisory transaction lock also serializes each applied batch with dual-write imports.
- `--after-id` resumes applied work safely because completed rows no longer have `legacy` state. A partial dry run resumed at a nonzero cursor cannot include earlier still-legacy fingerprints unless the same process retained them; restart dry-run at zero for authoritative duplicate counts.
- Quarantine reasons are fixed labels. Logs and command output must never include exceptions containing values, request bodies, key material, ciphertext, fingerprints, or legacy credential text.
- Keep old encryption key versions mounted until count and restore evidence proves no retained row or backup needs them.
