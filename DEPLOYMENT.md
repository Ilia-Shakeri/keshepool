# Keshepool Deployment

## Ingress contract

Keshepool uses one public origin. The browser calls same-origin `/api`; no public backend URL is compiled into client code.

Only `frontend` joins `caddy_gateway_net`. The edge proxy sends the whole public host to `keshepool-frontend:3000`. Next forwards these paths to `http://backend:8000` on the private Compose network:

- `/api/*`
- `/webhook/*`
- `/static/*`
- `/health/*`

The backend, PostgreSQL, and Redis are not public ingress targets. Create the shared proxy network once:

```sh
docker network create caddy_gateway_net
```

Example Caddy site block:

```caddyfile
keshepool.example.com {
    reverse_proxy keshepool-frontend:3000
}
```

The Caddy container must also join `caddy_gateway_net`. Replace the sample host in `.env` with the same HTTPS origin for `WEBHOOK_URL` and `WEB_APP_URL`.

## Image and migration policy

CI tests source first, upgrades both a fresh PostgreSQL database and a disposable legacy-uppercase-enum database, then publishes both images with one immutable commit tag:

```text
REGISTRY_IMAGE/backend:<full-commit-sha>
REGISTRY_IMAGE/frontend:<full-commit-sha>
```

Compose builds local images by default and consumes the explicit immutable image pair exported by `deploy.sh` in production. `deploy.sh` is the sole production migration owner; the backend entrypoint only starts the server. Do not run a second `alembic upgrade head` during the same release.

The deployment order is:

1. Pull the matching backend and frontend images.
2. Require PostgreSQL health and record Redis degradation when its database fallback is active.
3. Repair persistent static-directory ownership for the non-root backend user.
4. Stop frontend, then backend, to enter a short migration maintenance window.
5. Run the legacy baseline check and `alembic upgrade head` once.
6. Start and verify the exact backend image, then wait for readiness.
7. Start and verify the exact frontend image, then wait for readiness.
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

`IMAGE_TAG` must be a full 40-character commit SHA. The script rejects mutable tags such as `latest` by construction. It also validates Compose configuration, the host `.env`, and the external Caddy network before changing application containers.

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

`/health/live` proves the process is alive. `/health/ready` checks required dependencies and reports cache degradation according to backend policy. Frontend health uses the same-origin readiness proxy, so the proxy is not marked healthy while the backend is unavailable.

`smoke.sh` runs from the frontend container and verifies:

- backend readiness over Compose service DNS;
- readiness and public config through Next;
- protected products return an authorization error without Telegram init data;
- the same checks through the public HTTPS origin.

## Rollback

Before cutover, `deploy.sh` records the current backend and frontend image references. A failure before Alembic starts restores that pair. Once `alembic upgrade head` begins, the script never starts the old images automatically: migration 004 changes legacy enum labels to lowercase, and the old binary may not read or write those labels safely. Inspect with `docker compose run --rm --no-deps backend alembic current`, then recover with the same revision or a newer schema-compatible image.

Database migrations are never downgraded automatically because destructive rollback can lose data. This release therefore uses a short maintenance window for the one-time enum cutover instead of serving requests from incompatible binaries.

Keep the scheduled PostgreSQL backups and the persistent `pgdata`, `redisdata`, and `./static` data. If a migration itself requires data restoration, stop writes and perform a reviewed backup restore during a maintenance window; do not use an automatic downgrade on production data.
