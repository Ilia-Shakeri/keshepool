# Phase 1 design

## Durable administrator controls

Revision `008` is additive. It creates durable administrator identities, revocable role grants, hashed single-use confirmation nonces, approval requests, and unique approval votes. Environment administrator IDs remain break-glass superadmins during migration. `ADMIN_RBAC_ENABLED` defaults to `false`, so old operators keep access while grants are prepared and reviewed.

Nonce values are never stored directly. A nonce is bound to actor, chat, action, target type, target ID, and a short expiry. Consumption is one atomic conditional update. Wallet-credit and mass-catalog confirmations use this path now.

Approval payloads are bound by SHA-256 digest. The requester cannot cast the second approval, each actor can vote once, and execution is one atomic state change. The persistence service is not yet wired to bot flows, so dual approval is not ready for enablement.

Rollback keeps revision `008` in place and sets `ADMIN_RBAC_ENABLED=false`. Dropping the new tables is safe only before any grant or approval data becomes operational and only on a disposable database. Production rollback is forward-only.

## First safe slice

Referral attribution must use only the HMAC-validated `start_param` already returned by the server auth dependency. The old bootstrap request field remains accepted for compatibility but has no authority.

The server accepts only `ref_` plus 1 to 20 decimal digits with no leading zero. The frontend sends no referral value from unsafe browser data.

## Compatibility and rollback

- Database: no change.
- API: old request field remains accepted.
- Safe default: forged client referral values are ignored.
- Rollback: revert the referral parser, bootstrap call, and focused tests.

## Trust and session slice

- Main and admin webhooks use distinct secrets. The old setting is a non-production fallback only.
- General signed sessions last one hour. Money writes require a five-minute signature age.
- `AUTH_SESSION_EPOCH` is part of auth cache keys so an operator can invalidate all cached sessions.
- Browser caches are bound to a signed-session fingerprint and discard stale in-flight writes after identity change.
- Browser security policy starts report-only and can be enforced after telemetry review.

## Startup slice

API startup performs no webhook, command, menu, or group network calls in webhook mode. A separate idempotent management command owns that work and sends explicit update types.

Webhook HTTP input must be JSON, must fit the size bound, and must be an object before update validation. Durable inbox work stays additive in revision `007`.

## Inbox compatibility

- Revision `007` only adds `telegram_update_inbox`, constraints, and a claim index.
- API writes each validated update with database conflict-ignore on `(bot_type, update_id)` and returns fast.
- A separate worker claims due rows with `FOR UPDATE SKIP LOCKED`, records attempts, retries failed work, and recovers stale claims.
- Old code can run against the expanded schema because no old table or field changes.
- New code requires revision `007` and the worker. Roll back app and worker first; drop the inbox only on a disposable database or after operator approval.
- Feature state: durable inbox is the only webhook execution path and fails closed with 503 when PostgreSQL is unavailable.
