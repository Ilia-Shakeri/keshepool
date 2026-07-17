# Keshepool Deployment

## Ingress contract

Keshepool uses one public origin. The browser calls same-origin `/api`; no public backend URL is compiled into client code.

The `frontend` and `backend` services join `caddy_gateway_net`. Caddy sends `/health/ready` directly to the backend and all other public requests to `keshepool-frontend:3000`. Next forwards these application paths to `http://backend:8000` on the private Compose network:

- `/api/*`
- `/webhook/*`
- `/static/*`

Health routing stays separate: `/health/ready` is a backend-owned public route, while `/health/live` is served by the frontend process without a backend call.

The backend, PostgreSQL, and Redis are not public ingress targets. Create the shared proxy network once:

```sh
docker network create caddy_gateway_net
```

Use the full safe example in `ops/Caddyfile.example`. Its route shape is:

```caddyfile
keshepool.example.com {
    handle /health/ready {
        reverse_proxy keshepool-backend:8000
    }
    handle {
        reverse_proxy keshepool-frontend:3000
    }
}
```

The Caddy container must also join `caddy_gateway_net`. Replace the sample host in `.env` with the same HTTPS origin for `WEBHOOK_URL` and `WEB_APP_URL`.

## Image and migration policy

CI tests source first, upgrades both a fresh PostgreSQL database and a disposable legacy-uppercase-enum database, then publishes both images with one immutable commit tag:

```text
REGISTRY_IMAGE/backend:<full-commit-sha>
REGISTRY_IMAGE/frontend:<full-commit-sha>
```

Local Compose builds are for development only. The one supported production path is `sh ./deploy.sh` with registry images. It uses one full Git SHA for both images and passes that SHA to the frontend as `DEPLOYMENT_VERSION`. `deploy.sh` is the sole production migration owner; the backend entrypoint only starts the server. Do not run a second `alembic upgrade head` during the same release.

The deployment order is:

1. Pull the matching backend and frontend images.
2. Require PostgreSQL health and record Redis degradation when its database fallback is active.
3. Repair persistent static-directory ownership for the non-root backend user.
4. Stop frontend, then backend, to enter a short migration maintenance window.
5. Run the legacy baseline check and `alembic upgrade head` once.
6. Start and verify the exact backend image, then wait for readiness.
7. Start and verify the exact frontend image, wait for liveness, and confirm its reported deployment revision.
8. Verify service-DNS, same-origin, and public ingress routes with `smoke.sh`.

## Production release

Copy `.env.example` to `.env`, replace every placeholder, and set:

```env
REGISTRY_IMAGE=registry.example.com/group/keshepool
IMAGE_TAG=<full-commit-sha>
```

Log the host into the registry, then run:

```sh
sh ./deploy.sh
```

`IMAGE_TAG` must be a full 40-character commit SHA. The script rejects empty values, `local`, mutable tags, and the all-zero example placeholder. It validates Compose, both running image IDs, the frontend revision, the host `.env`, and the external Caddy network.

## Required CI variables

Store these as protected, masked variables where applicable:

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_PATH`
- `DEPLOY_SSH_PRIVATE_KEY`
- `DEPLOY_KNOWN_HOSTS`
- `PRODUCTION_URL`

The production job is manual and serialized. It copies only the revision's Compose and release scripts, logs the host into the registry through standard input, and deploys the exact pipeline commit.

## Admin authorization

`ADMIN_TELEGRAM_IDS` is the only user allowlist. It must contain numeric Telegram user IDs separated by commas. `ADMIN_GROUP_CHAT_ID` is optional. In that group, a sender must both appear in the user allowlist and currently hold Telegram administrator or creator status. Ordinary group members receive no admin access.

Tetra callbacks are authenticated through server-side payment verification using `TETRA98_API_KEY`; no undocumented signature header is assumed. A configured `CRYPTO_DEPOSIT_ADDRESS_USDT` requires `CRYPTO_WEBHOOK_SECRET`.

Set `USDT_TO_IRR_RATE` to a positive, operator-reviewed Toman fallback. It is used only when the manual override, cached live rate, and both live market sources are unavailable.

## Health and smoke behavior

`/health/live` proves only that the target process serves requests. Frontend container health calls this path, enforces a timeout, validates its body, and prints useful failure details. Frontend `/health/ready` separately checks backend contact and reports unavailable, timeout, and malformed-response failures. Public Caddy `/health/ready` stays directed to the backend.

`smoke.sh` runs from the frontend container and verifies:

- backend readiness over Compose service DNS;
- readiness and public config through Next;
- protected products return an authorization error without Telegram init data;
- the same checks through the public HTTPS origin.

## Rollback

Before cutover, `deploy.sh` records the current backend and frontend image references. A failure before Alembic starts restores that pair. Once `alembic upgrade head` begins, the script never starts the old images automatically: migration 004 changes legacy enum labels to lowercase, and the old binary may not read or write those labels safely. Inspect with `docker compose run --rm --no-deps backend alembic current`, then recover with the same revision or a newer schema-compatible image.

Database migrations are never downgraded automatically because destructive rollback can lose data. This release therefore uses a short maintenance window for the one-time enum cutover instead of serving requests from incompatible binaries.

Keep the scheduled PostgreSQL backups and the persistent `pgdata`, `redisdata`, and `./static` data. If a migration itself requires data restoration, stop writes and perform a reviewed backup restore during a maintenance window; do not use an automatic downgrade on production data.

## Backup verification

The backup image creates rotating compressed SQL dumps and `*-latest.sql.gz` pointers. Compose runs `scripts/check-backup.sh` to check directory writability, non-zero size, gzip integrity, readable dump data, and an eight-hour maximum age for the six-hour schedule. Docker keeps the container in its startup grace period until the first scheduled backup; an earlier valid latest backup can pass at once.

Run the same read-only operator check:

```sh
docker compose exec db-backup /bin/sh /usr/local/bin/check-backup
```

Set `BACKUP_MAX_AGE_SECONDS` only when the schedule changes. This check never restores into production and never deletes a backup.

## Caddy log migration

The production Caddy project is outside this repository. Copy the log filter and route blocks from `ops/Caddyfile.example` into that project. The filters cover runtime/error logs and access logs while keeping normal status, duration, and proxy facts. They remove the named sensitive request headers and `Set-Cookie` before encoding.

Validate, inspect, then reload:

```sh
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile --pretty
caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Send a probe with `redaction-probe` in each sensitive header. Confirm that marker is absent from access and error output while ordinary access rows remain visible.

## Source export and secret scan

Run `sh ./scripts/export-source.sh` to build a source archive from an explicit tracked-file allowlist. Its staging pass removes environment files, keys, certificates, backups, database dumps, token files, generated archives, build output, dependencies, and repository metadata. Static inventory seed data is not in the allowlist. CI scans Git history and the work tree with default secret rules plus narrow fake-value exceptions.

## Host Redis setting

The production host requires persistent `vm.overcommit_memory = 1`. The host operator owns this setting. Application containers stay unprivileged and do not call `sysctl` or alter kernel settings at startup.

## Unexpected action requests

This frontend defines no server-side form actions. A missing action ID is treated as a stale, malformed, or mixed-deployment request. The request proxy logs only method, pathname, deployment revision, and header presence. It does not log the header value, cookies, authorization data, Telegram init data, or request bodies.
