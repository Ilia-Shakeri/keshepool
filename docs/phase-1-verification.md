# Phase 1 verification

## Passed locally

- Main secret cannot authenticate an admin webhook.
- Production requires two distinct webhook secrets; legacy fallback is non-production only.
- Financial init data older than five minutes is rejected before cache lookup.
- Auth cache keys include the configured session epoch.
- Browser cache resets on signed-session change and stale reads cannot repopulate the new session cache.
- API lifespan source has no webhook, command, or menu configuration calls.
- Webhook content type and JSON object shape are bounded.
- Duplicate HTTP results are acknowledged without dispatcher work.
- Browser and edge header tests preserve Telegram embedding and avoid a deny-frame header.
- Revision `007`, model constraints, worker modules, Compose worker, and explicit configuration job compile and parse.

## Blocked proof

- The PostgreSQL duplicate-race and migration tests are present but skipped without a disposable service.
- Docker worker lifecycle, Telegram delivery, edge routing, and report-only policy telemetry are not live-tested here.
- Migration `008` adds durable identities, role grants, one-use action nonces, and two-person approval records. Wallet-credit and mass-catalog confirmations now consume actor/chat/action/target-bound nonces. Durable role lookup is present but remains behind `ADMIN_RBAC_ENABLED=false` for the additive release.
- Two-person approval persistence and service rules are tested, but bot flows do not yet create and complete approval requests. Do not enable a dual-approval cutover until those flows and disposable PostgreSQL races pass.
