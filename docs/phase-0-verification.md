# Phase 0 verification

## Local proof

- Repository path guard passed.
- Source export shell syntax passed.
- A clean temporary Git repository exported 417 allowlisted entries.
- The exported tree secret scan passed with no findings.
- The extracted backend source compiled.
- The extracted frontend completed clean install and production build on Node 22.
- Backend suite passed: 110 tests, 5 service-backed tests skipped.
- Frontend passed: 19 tests, typecheck, lint, and production build.
- All temporary clean-export and clean-build folders were removed after their paths were checked.

## Blocked proof

- Docker Compose config and image builds: Docker is not installed.
- Fresh and revision-006 database upgrades: no disposable PostgreSQL service.
- History scan: failed on two old bot-token-shaped values in `.env.example` history. Values stayed redacted.

## Release block

Operator must revoke affected credentials, purge unsafe refs and artifacts, review incident records, and sign off. Local code work cannot complete those acts.
