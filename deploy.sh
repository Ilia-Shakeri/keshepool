#!/bin/bash
set -e

echo "🛑 Pulling latest infrastructure updates..."
git pull origin main

echo "🏗️ Pulling latest container images..."
docker compose pull

echo "🚀 Starting services..."
docker compose up -d

echo "🗄️ Executing Alembic database migrations..."
docker compose exec backend alembic upgrade head

echo "🧹 Pruning dangling Docker images to save VPS storage..."
docker image prune -f

echo "✅ Admin Bot & Keshepool Mini-app are fully operational."