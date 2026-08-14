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
- Browser policy tests prove nonce validation, enforced script rules, the Telegram bridge host and frame ancestors, blocked script attributes, no `unsafe-eval`, and only style-attribute `unsafe-inline`.
- The page shell is dynamic, sends `private, no-store`, gives the Telegram bridge the request nonce, and leaves Caddy free of a duplicate static policy.
- The optimized production build marks every page as dynamic. Two sequential local production responses returned different policy nonces; all 17 script tags in the sampled page carried the matching response nonce, the Telegram bridge declaration was present, and no report-only header was returned.
- Revision `007`, model constraints, worker modules, Compose worker, and explicit configuration job compile and parse.
- Revision `011` adds bounded claim tokens. Focused tests prove unique per-claim fences, fenced heartbeats and terminal writes, the attempt ceiling, and payload erasure rules.
- Public webhook, callback, admin, bootstrap, checkout, cashout, credential-reveal, and ordinary-read policies have focused path tests.
- Sensitive ingress fails closed when Redis is unavailable; ordinary API reads continue.
- Traffic readiness returns `503` when either PostgreSQL or Redis is unavailable. Liveness remains independent.
- Sensitive policy concurrency leases use one Redis acquisition script, token-fenced release, stale-token score cleanup, and crash TTL. Focused tests prove cap rejection, backend failure, normal release, and exception-path release.
- Optional Tetra and crypto callback CIDRs use the hardened effective client IP. Focused tests prove blank-list compatibility, allowed source matching, denied sources, and malformed-configuration fail-closed behavior.
- Spoofed forwarding headers from untrusted peers and multi-address chains do not select the rate-limit identity.
- The frontend proxy strips client provenance and rebuilds one validated edge IP. Caddy strips nonstandard client-address headers and redacts both callback signature headers.
- The example Caddyfile passes checksum-verified Caddy 2.11.4 validation and adaptation.
- Checkout and order-list responses contain masked credential metadata only.
- Credential reveal uses fresh owner auth, fails closed when its limiter is unavailable, locks the owned order, enforces a durable configured count, records allowed and database-reached denied outcomes without the revealed value, rejects unavailable states and oversized values, emits no-store headers, and commits event plus scrubbed audit rows before returning.
- Order pagination keeps the array body, uses descending timestamp-and-ID boundaries, returns a validated opaque next cursor header, and caps each page. Tie-boundary tests prove no page gap or overlap.
- Frontend order and checkout views use the separate reveal POST and clear revealed modal state on close. The order page fences stale requests, deduplicates appended IDs, and keeps the current rows on next-page failure.
- Notification tests prove the old mark-all route remains, one-row acknowledgement is owner-scoped and idempotent, and bulk acknowledgement cannot cross the supplied positive bounded ID or the current owner.
- Compose source contracts prove the internal-only data plane, gateway-only frontend, data-plus-egress worker, egress-only configuration job, and networkless static initializer. The migration job no longer receives runtime bot, webhook, cache, provider, or administrator credentials.
- Referral unit tests prove fixed opaque-code parsing, numeric legacy rejection, ignored body attribution, random code shape, conflict retry, insert-bound attribution, and no re-attribution. Model and migration tests prove the unique format checks, self-reference guard, revision `013` chain, and immutable-attribution trigger source.
- Frontend tests prove invite links require the server profile referral code and never fall back to browser Telegram identity.

## Blocked proof

- The PostgreSQL duplicate-race, claim-fence, attempt-cap, payload-erasure, and migration tests are present but skipped without a disposable service.
- The revision `013` PostgreSQL winner/re-attribution test is present but skipped without a disposable service. Keep H-15 in progress until migration upgrade and this race test pass there.
- The revision `014` model and migration shape pass locally. Its real PostgreSQL concurrent reveal test is present but skipped without a disposable service. Keep H-24 in progress until that race, upgrade, and replacement-lifecycle checks pass on a release-shaped database.
- Docker worker lifecycle, Telegram delivery, and edge routing are not live-tested here.
- Docker is unavailable on this workstation, so `docker compose config` and live container network-resolution probes remain release-host checks. Local YAML parsing and 41 focused isolation/ingress tests pass.
- Migration `008` adds durable identities, role grants, one-use action nonces, and two-person approval records. Wallet-credit and mass-catalog confirmations now consume actor/chat/action/target-bound nonces. Durable role lookup is present but remains behind `ADMIN_RBAC_ENABLED=false` for the additive release.
- Wallet-credit and mass-catalog bot flows now create and complete payload-bound two-person approval requests. The requester cannot approve, the second actor must use the configured group, and one atomic status transition blocks replay. The real PostgreSQL concurrency test remains skipped unless a disposable `TEST_DATABASE_URL` is supplied, so keep `ADMIN_DUAL_APPROVAL_ENABLED=false` until that proof passes.
- Production effective-client behavior still needs a probe through the real Caddy and frontend container addresses. Set `TRUSTED_PROXY_IPS` before that test; never use a wildcard or a broad private range.
- Shared in-flight caps are present, but real multi-instance Redis/edge behavior is not proved. Provider CIDR lists stay blank until stable provider-owned networks are contractually confirmed. Mutual TLS is not configured, so M-48 stays in progress.
- Inbox execution remains at least once across external side effects. Handler-specific durable idempotency proof is still required before any exactly-once claim.
- The enforced browser policy still needs an actual launch in Telegram web, desktop, Android, and iOS shells. There is no bounded central violation collector yet, so H-30 remains in progress even when local build and response checks pass.
