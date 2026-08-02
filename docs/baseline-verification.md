# Baseline verification

Date: 2026-08-02
Revision: `ace3deb28d965caccd688200040ca8915999f5ec`
Branch: `main`
Work tree before changes: clean

## Safety boundary

- No live host, database, cache, bot, payment provider, chain service, or customer account was used.
- Backend tests used fake local-only service URLs and fake test keys.
- No secret value was printed or copied.
- A work branch could not be made because `.git/refs` is read-only in this workspace. Work remains uncommitted on `main`.

## Host

| Tool | Result |
| --- | --- |
| Python | 3.14.5 |
| Project virtual Python | 3.12.10 |
| Node | 22.23.0 |
| npm | 10.9.8 |
| Docker | blocked; command not installed |
| POSIX shell | Git for Windows shell found after initial subsystem failure |
| Gitleaks | initially absent; pinned 8.30.1 fetched to a temporary tool folder and hash-checked |

## Checks

| Check | Result |
| --- | --- |
| `docker compose --env-file .env.example config --quiet` | blocked; Docker absent |
| shell syntax checks | pass with Git for Windows shell |
| `python -m compileall backend/app backend/alembic backend/tests backend/scripts` | pass with project Python 3.12 |
| `python -m pyflakes backend/app backend/alembic backend/tests backend/scripts` | pass with project Python 3.12 |
| `alembic upgrade head` | blocked; no disposable PostgreSQL service |
| `pytest -q` | pass; 106 passed, 5 PostgreSQL tests skipped, 2 dependency warnings |
| `npm.cmd ci --legacy-peer-deps` | pass; 646 packages, 0 known vulnerabilities |
| `npm.cmd run test` | pass; 19 passed |
| `npm.cmd run typecheck` | pass |
| `npm.cmd run lint` | pass; first two contended runs hit the host limit, isolated run passed in 18.2 seconds |
| `npm.cmd run build` | pass; Next.js 16.2.7 production build |
| Gitleaks history scan | fail; two old bot-token-shaped values found in `.env.example` history; redacted |
| Gitleaks raw work-tree scan | fail; ignored local env plus generated dependency/build files found; redacted |
| Gitleaks deliverable scan | pass; tracked plus non-ignored new files had no findings |

## Release meaning

Local checks do not prove migration, concurrency, proxy, container, restore, payment, bot, weak-network, or staging behavior. Release stays blocked until the missing checks run on disposable services and operator incident work is signed off.
