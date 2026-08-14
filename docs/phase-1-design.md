# Phase 1 design

## Durable administrator controls

Revision `008` is additive. It creates durable administrator identities, revocable role grants, hashed single-use confirmation nonces, approval requests, and unique approval votes. Environment administrator IDs remain break-glass superadmins during migration. `ADMIN_RBAC_ENABLED` defaults to `false`, so old operators keep access while grants are prepared and reviewed. `ADMIN_ENV_BREAK_GLASS_ENABLED` defaults to `true`; after role enforcement and grants are proved, an operator may turn it off in a separate release so environment IDs become revocable database-controlled identities.

When role enforcement is enabled, catalog handlers require `catalog`, transaction handlers require `finance` or read-only `auditor`, user and messaging handlers require `support`, cashout reads allow `support` or `finance`, cashout state writes require `finance`, and rate controls require `finance`. Break-glass IDs act as `superadmin`. The role management command is local-only and records grants and revocations in the admin audit log.

Authorization tables store only nonce hashes. A nonce is bound to actor, chat, action, target type, target ID, and a short expiry. Telegram callback bytes can exist briefly in the durable inbox while an update is pending; revision `011` clears the whole payload after success or terminal failure. Consumption is one atomic conditional update. Wallet-credit and mass-catalog confirmations use this path now.

Revision `011` adds a random claim token to each inbox lease. Heartbeats renew only the current token, and stale workers cannot mark a reclaimed row done or failed. The final allowed stale lease becomes terminal instead of receiving an extra try. This is fenced at-least-once processing: each handler that reaches an outside side effect still needs its own durable idempotency key.

Approval payloads are bound by SHA-256 digest. The requester cannot cast the second approval, each actor can vote once, and execution is one atomic state change. Wallet credits above the configured threshold and mass catalog removal use this service. The second administrator must act in the configured group and approve an unchanged transaction or catalog snapshot. `ADMIN_DUAL_APPROVAL_ENABLED` defaults to `false` until grants and disposable database races are reviewed.

Rollback keeps revision `008` in place and sets `ADMIN_RBAC_ENABLED=false`. Dropping the new tables is safe only before any grant or approval data becomes operational and only on a disposable database. Production rollback is forward-only.

## Opaque referral attribution

Revision `013` adds one unique, random 128-bit lowercase hexadecimal referral code to every user. New and backfilled values come from independent cryptographic random sources. The public link contains `ref_` plus exactly 32 lowercase hexadecimal characters and exposes no Telegram user ID.

Attribution reads only the HMAC-validated `start_param` returned by the server auth dependency. The old bootstrap body field remains accepted for wire compatibility but has no authority. Numeric legacy parameters, mixed-case values, malformed lengths, banned referrers, and self-referrals are ignored.

The chosen referrer is written in the same conflict-safe user insert. Concurrent first bootstraps can create only one user row, so only the winning insert supplies attribution. Existing users are never re-attributed. A database check blocks self-reference, and a trigger prevents a non-null attribution from being cleared or changed.

## Compatibility and rollback

- Database: revision `013` adds one column, two checks, one unique constraint, and an attribution-protection trigger. Existing user rows receive unique opaque codes during the additive column operation.
- API: `user.referralCode` is additive. The old request field remains accepted and ignored.
- Safe default: malformed, numeric, unsigned-body, self, banned, and re-attribution attempts grant no attribution.
- Rollout: apply `013` before serving the new backend profile and invite page. Numeric links already in circulation intentionally stop granting attribution; there is no numeric compatibility fallback.
- Rollback: production is forward-only after opaque links are issued. Disable invitation entry points while fixing forward. Use the `013` downgrade only on a disposable database, and never restore numeric attribution.

## Trust and session slice

- Main and admin webhooks use distinct secrets. The old setting is a non-production fallback only.
- General signed sessions last one hour. Money writes require a five-minute signature age.
- `AUTH_SESSION_EPOCH` is part of auth cache keys so an operator can invalidate all cached sessions.
- Browser caches are bound to a signed-session fingerprint and discard stale in-flight writes after identity change.
- Browser HTML gets an enforced, per-request nonce policy from the frontend proxy. Static edge policy is not used because a second policy cannot share the generated nonce.

## Startup slice

API startup performs no webhook, command, menu, or group network calls in webhook mode. A separate idempotent management command owns that work and sends explicit update types.

Webhook HTTP input must be JSON, must fit the size bound, and must be an object before update validation. The base durable inbox stays additive in revision `007`; revision `011` adds claim fencing without rewriting old rows.

## Credential access boundary

Checkout and order-list responses expose only a fixed masked preview and `credentialAvailable`; they never include the stored plaintext. The existing inventory column remains unchanged until the separate encrypted-vault migration is designed and proved.

An owner can request `POST /api/orders/{public_id}/reveal-credential` only with the stricter five-minute signed-auth dependency. The endpoint validates the bounded public ID, applies a fail-closed per-user Redis limit, locks the owned order row, checks that the active order and assigned inventory belong to the same user, and rejects oversized values. Revision `014` adds a durable per-order counter with a database hard cap of 100 plus an outcome-only reveal event table. The runtime cap defaults to five. Allowed and database-reached denied attempts write an event and redacted administrator audit record, and the transaction commits before a value returns. Event rows contain no revealed value. Responses send `no-store`, `no-cache`, and expiry headers. The frontend holds a revealed value only in modal state and clears it when the modal closes.

`GET /api/orders` keeps its array response for old clients but now defaults to 20 rows and caps requests at 50. Rows use descending `(created_at, id)` order. A fixed-length validated cursor applies the matching timestamp-and-ID boundary, and `X-Next-Cursor` carries the next page token. The browser deduplicates appended order IDs, fences stale page requests, and preserves the current page when a next-page request fails.

This slice bounds repeated exposure and unbounded order reads. H-24 remains in progress until the replacement lifecycle and release-database migration proof are complete. Encrypted backup protection remains separate.

## Notification acknowledgement

The old mark-all notification route remains compatible. An owner-scoped per-notification route is idempotent, returns not found for another owner's row, and accepts only a positive bounded integer ID. The bulk route acknowledges unread rows for the current owner only through a positive bounded notification ID, so a client can persist one stable high-water mark without marking later arrivals.

## Inbox compatibility

- Revision `007` only adds `telegram_update_inbox`, constraints, and a claim index.
- API writes each validated update with database conflict-ignore on `(bot_type, update_id)` and returns fast.
- A separate worker claims due rows with `FOR UPDATE SKIP LOCKED`, records attempts, retries failed work, and recovers stale claims.
- Revision `011` gives every claim a random lease token. Heartbeats renew the lease while work runs, including rows waiting in a claimed batch. Completion and failure writes require the same token, so an old worker cannot change a newer claim.
- Rows at the attempt ceiling cannot be claimed again. A stale last attempt becomes terminal, and completed or terminal rows replace the update payload with an empty object. Revision `011` also erases payloads already held by old completed and terminal rows; downgrade cannot restore erased payload data.
- Old code can run against the expanded schema because no old table or field changes.
- New worker code requires revisions `007` and `011`. Roll back app and worker before dropping the optional claim-token column; drop the inbox only on a disposable database or after operator approval.
- Feature state: durable inbox is the only webhook execution path and fails closed with 503 when PostgreSQL is unavailable.

Inbox delivery is at least once, not exactly once across external side effects. A process can finish an external action and die before saving completion. Claim fencing blocks stale database writes but cannot undo that action. Each side-effecting handler still needs a durable idempotency key tied to bot type and update ID.

## Public ingress controls

Caddy is the first public proxy. It drops nonstandard client-address headers and uses its built-in behavior to rebuild `X-Forwarded-For`, `X-Forwarded-Host`, and `X-Forwarded-Proto`. The frontend proxy removes every incoming forwarding/client-address header, accepts at most one valid edge IP, and rebuilds only the three standard headers before a browser API request reaches the backend.

`TRUSTED_PROXY_IPS` must contain only the exact Caddy and frontend proxy addresses or their narrowly reviewed network ranges. The ingress limiter accepts a single forwarded IP only when the immediate peer matches that setting. It rejects forwarding chains and ignores all forwarding headers from an untrusted peer.

The shared Redis limiter runs before route dependencies and request-body parsing. These per-client ceilings are coarse abuse guards; authenticated endpoints keep their stricter per-user limits. Every fail-closed policy also acquires a shared Redis in-flight lease before route dispatch. Acquisition removes expired leases, counts and adds the new random lease in one Redis script. The middleware removes only its own token after route completion, and each token carries an expiry score plus a key TTL so a crashed worker cannot consume capacity forever. `INGRESS_SENSITIVE_MAX_IN_FLIGHT` defaults to `64` per policy and `INGRESS_IN_FLIGHT_TTL_SECONDS` defaults to `120`.

| Ingress class | Requests per minute | Redis unavailable |
| --- | ---: | --- |
| Main webhook | 600 | reject with 503 |
| Admin webhook | 300 | reject with 503 |
| Payment callback | 300 | reject with 503 |
| Internal admin API | 120 | reject with 503 |
| Auth bootstrap | 300 | reject with 503 |
| Checkout and payment creation | 120 | reject with 503 |
| Cashout creation | 60 | reject with 503 |
| Credential reveal | 60 | reject with 503 |
| Ordinary API read | 600 | continue to database path |

Rate or concurrency rejection returns `429`, `Retry-After`, and `Cache-Control: no-store`. Sensitive paths fail closed with `503` when Redis cannot make either rate or concurrency decisions. Caddy also applies a 1 MB body ceiling to both bot webhooks and both payment callback paths.

`TETRA98_CALLBACK_ALLOWED_CIDRS` and `CRYPTO_CALLBACK_ALLOWED_CIDRS` are optional exact IPv4/IPv6 source networks. A configured list is matched against the same hardened effective client IP used by the limiter. An invalid list fails application validation and also fails callback requests closed if configuration is altered after startup. Both lists default blank because provider-owned address contracts are not known; blank preserves signed-callback behavior.

M-48 remains in progress until each provider supplies and the operator verifies a stable CIDR or mutual-TLS contract, and until the real Caddy/frontend/backend path proves effective client identity, cap sharing, and callback delivery. Rollback may blank the provider lists and remove the ingress middleware and proxy header blocks without a schema change.

## Browser content policy

The frontend proxy creates a new UUID-based nonce for every page request. It places the enforced policy on both the request passed to the renderer and the browser response. The renderer is forced dynamic, page responses are private and `no-store`, and the Telegram bridge script receives that same validated nonce explicitly. The local framework runtime also reads the request policy and applies the nonce to its own scripts and generated style elements.

Inline script and script attributes are blocked. `unsafe-eval` is absent. Existing React style attributes still require `style-src-attr 'unsafe-inline'`; style elements require the nonce. Only same-origin scripts and the Telegram bridge host are named. Frame ancestors remain limited to this origin and Telegram origins used by the web client.

Caddy does not add a second content policy. Multiple enforced policies intersect, and a static edge policy cannot know the per-request nonce. Caddy keeps transport, referrer, permission, MIME, routing, body-limit, and log-redaction controls.

No violation collector is enabled yet. An unauthenticated local log endpoint would add a flood and log-injection surface, while the current edge has no shared report-rate control. A release operator must add a bounded central collector before policy telemetry can be retained. H-30 stays in progress until the real Telegram web, desktop, Android, and iOS shells prove the enforced policy and the bridge script.

Emergency rollback must revert the frontend proxy policy and the explicit script nonce together. Do not add a static enforced nonce policy at Caddy.
