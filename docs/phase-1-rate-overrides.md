# Durable USDT rate override

Revision `009` adds one PostgreSQL source row plus append-only version rows for every manual set or clear. Each version stores the rate state, actor when supplied, change source, and time. The singleton row is updated with a PostgreSQL upsert, so concurrent changes receive distinct ordered versions.

`apply_usdt_rate_override_in_session(...)` stages the singleton update, version row, and administrator audit row without committing. It rejects calls while the durable feature flag is off. Privileged callers must consume the bound approval and call this function with the same session, then commit once. When an actor is supplied, the audit row is always flushed in that transaction. After a successful commit, call `cache_usdt_rate_override(state)`. Never refresh Redis before the commit succeeds. The compatibility `set_usdt_rate(...)` and `clear_usdt_rate_override(...)` wrappers perform this commit-then-cache order themselves.

`OPERATIONS_RATE_DB_ENABLED` defaults to `false`. While false, reads and writes keep the old Redis contract. After revision `009` is applied, enable the flag on all application processes together. The first read imports a valid legacy Redis override when PostgreSQL has no source row. New writes commit PostgreSQL first, then refresh the old Redis key and a five-minute versioned cache. A database read wins over stale Redis data. During a database outage, only the short-lived versioned cache may supply an override; an indefinite legacy value cannot become authority.

Rollback is flag-first: set `OPERATIONS_RATE_DB_ENABLED=false`. Keep revision `009` and its audit rows. Drop the tables only on a disposable database or before any operational version exists.
