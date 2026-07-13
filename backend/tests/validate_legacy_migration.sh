#!/bin/sh
set -eu

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"

legacy_database="${POSTGRES_DB}_legacy"
legacy_url="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${legacy_database}"

export PGPASSWORD="$POSTGRES_PASSWORD"
createdb --host=db --username="$POSTGRES_USER" "$legacy_database"

DATABASE_URL="$legacy_url" alembic upgrade 003

# Reproduce databases whose enum types were created from Python member names.
psql --host=db --username="$POSTGRES_USER" --dbname="$legacy_database" --set=ON_ERROR_STOP=1 <<'SQL'
DO $migration$
DECLARE
    label record;
BEGIN
    FOR label IN
        SELECT type_info.typname, enum_info.enumlabel
        FROM pg_type AS type_info
        JOIN pg_enum AS enum_info ON enum_info.enumtypid = type_info.oid
        WHERE type_info.typname IN (
            'itemstatus',
            'transactiontype',
            'transactionstatus',
            'orderstatus',
            'cashoutrequeststatus'
        )
    LOOP
        EXECUTE format(
            'ALTER TYPE %I RENAME VALUE %L TO %L',
            label.typname,
            label.enumlabel,
            upper(label.enumlabel)
        );
    END LOOP;
END
$migration$;
SQL

DATABASE_URL="$legacy_url" alembic upgrade head

uppercase_count="$(
  psql --host=db --username="$POSTGRES_USER" --dbname="$legacy_database" --tuples-only --no-align \
    --command="SELECT count(*) FROM pg_enum AS enum_info JOIN pg_type AS type_info ON type_info.oid = enum_info.enumtypid WHERE type_info.typname IN ('itemstatus', 'transactiontype', 'transactionstatus', 'orderstatus', 'cashoutrequeststatus') AND enum_info.enumlabel <> lower(enum_info.enumlabel)"
)"

if [ "$uppercase_count" != "0" ]; then
  echo "Legacy enum migration left $uppercase_count uppercase labels." >&2
  exit 1
fi

echo "Legacy uppercase enum migration reached head with canonical labels."
