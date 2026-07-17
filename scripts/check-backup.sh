#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-/backups}"
max_age_seconds="${BACKUP_MAX_AGE_SECONDS:-28800}"

if [ ! -d "$backup_dir" ] || [ ! -w "$backup_dir" ]; then
  echo "backup check failed: $backup_dir is not writable" >&2
  exit 1
fi

latest=""
latest_mtime=0
for candidate in "$backup_dir"/last/*-latest.sql.gz "$backup_dir"/*-latest.sql.gz; do
  [ -e "$candidate" ] || continue
  candidate_mtime="$(stat -c %Y "$candidate" 2>/dev/null || echo 0)"
  if [ "$candidate_mtime" -gt "$latest_mtime" ]; then
    latest="$candidate"
    latest_mtime="$candidate_mtime"
  fi
done

if [ -z "$latest" ]; then
  echo "backup check failed: no *-latest.sql.gz file exists" >&2
  exit 1
fi

if [ ! -s "$latest" ]; then
  echo "backup check failed: latest backup is empty" >&2
  exit 1
fi

if ! gzip -t "$latest"; then
  echo "backup check failed: gzip integrity check failed" >&2
  exit 1
fi

now="$(date +%s)"
age_seconds=$((now - latest_mtime))
if [ "$age_seconds" -lt 0 ] || [ "$age_seconds" -gt "$max_age_seconds" ]; then
  echo "backup check failed: latest backup age is ${age_seconds}s; max is ${max_age_seconds}s" >&2
  exit 1
fi

preview="$(gzip -dc "$latest" 2>/dev/null | head -c 1024)"
if [ -z "$preview" ]; then
  echo "backup check failed: dump has no readable SQL data" >&2
  exit 1
fi

size_bytes="$(stat -c %s "$latest")"
echo "backup check ok: file=$latest size=${size_bytes}B age=${age_seconds}s gzip=valid dump=readable"
