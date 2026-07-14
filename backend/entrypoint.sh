#!/bin/sh
set -e

echo "[entrypoint] Checking migration baseline..."
python3 /app/scripts/stamp_if_legacy.py

echo "[entrypoint] Running database migrations..."
alembic upgrade head

echo "[entrypoint] Starting application server..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips "*"
