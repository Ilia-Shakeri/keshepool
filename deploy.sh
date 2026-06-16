#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "🛑 Pulling latest infrastructure updates..."
git pull origin main

echo "🏗️ Rebuilding Docker containers silently..."
# The --build flag ensures any new requirements are installed
# The -d flag runs them in the background
docker compose up -d --build

echo "🗄️ Executing Alembic database migrations..."
# Execute the migration inside the running backend container
docker compose exec backend alembic upgrade head

echo "🧹 Pruning dangling Docker images to save VPS storage..."
docker image prune -f

echo "✅ Aegis Node & Keshepool are fully operational."