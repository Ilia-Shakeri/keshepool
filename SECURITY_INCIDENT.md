# Mandatory Credential Exposure Response

The original source export contained production-looking credentials. Source edits do not revoke or rotate external credentials. Production release is blocked until an operator completes and records every item below.

## Required operator actions

- [ ] Revoke both Telegram bot tokens, issue replacements, and update the protected deployment secret store.
- [ ] Rotate the PostgreSQL password and update both the database role and protected deployment secret store.
- [ ] Revoke and replace the payment-provider key.
- [ ] Replace the Telegram webhook secret and re-register both bot webhooks.
- [ ] Replace every payment-provider webhook secret.
- [ ] Replace the crypto webhook secret.
- [ ] Replace the internal administrator API key, even when the internal API remains disabled.
- [ ] Purge exposed values and source exports from Git history, CI artifacts, job logs, caches, backups, release archives, chat attachments, and operator workstations.
- [ ] Invalidate old CI variables, deployment files, and cached container layers that may contain exposed values.
- [ ] Run the redacted history and work-tree scans after the purge.
- [ ] Review provider, Telegram, database, and administrator audit logs for misuse from the first possible exposure time.
- [ ] Record the operator, completion time, affected systems, and new secret version identifiers in the private incident system. Do not place secret values in this repository.

## Release gate

Do not mark this incident complete from a source change alone. A designated operator must confirm all checklist items in the private incident record. Keep this repository checklist unmarked unless that confirmation has occurred.

## Safe scan commands

```sh
gitleaks git . --config .gitleaks.toml --redact --verbose
gitleaks dir . --config .gitleaks.toml --redact --verbose
```

Never upload a finding report that contains unredacted values.
