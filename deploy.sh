#!/bin/sh
set -eu

read_env_value() {
  key="$1"
  if [ -f .env ]; then
    sed -n "s/^${key}=//p" .env | tail -n 1
  fi
}

REGISTRY_IMAGE="${REGISTRY_IMAGE:-$(read_env_value REGISTRY_IMAGE)}"
IMAGE_TAG="${IMAGE_TAG:-$(read_env_value IMAGE_TAG)}"

: "${REGISTRY_IMAGE:?Set REGISTRY_IMAGE to the project registry path.}"
: "${IMAGE_TAG:?Set IMAGE_TAG to the full commit SHA.}"

if ! printf '%s' "$IMAGE_TAG" | grep -Eq '^[0-9a-f]{40}$'; then
  echo "[deploy] IMAGE_TAG must be a full immutable commit SHA." >&2
  exit 2
fi

if [ ! -f .env ]; then
  echo "[deploy] .env is required on the deployment host." >&2
  exit 2
fi

export BACKEND_IMAGE="${REGISTRY_IMAGE}/backend:${IMAGE_TAG}"
export FRONTEND_IMAGE="${REGISTRY_IMAGE}/frontend:${IMAGE_TAG}"

docker compose version >/dev/null
docker network inspect caddy_gateway_net >/dev/null 2>&1 || {
  echo "[deploy] Create the external caddy_gateway_net network before deployment." >&2
  exit 2
}
mkdir -p backups static
docker compose config --quiet

previous_backend_image="$(docker inspect --format '{{.Config.Image}}' keshepool-backend 2>/dev/null || true)"
previous_frontend_image="$(docker inspect --format '{{.Config.Image}}' keshepool-frontend 2>/dev/null || true)"
application_replaced=false
cutover_started=false
migration_started=false
schema_changed=false
deployment_complete=false

wait_for_health() {
  service="$1"
  timeout_seconds="$2"
  start_time="$(date +%s)"

  while :; do
    container_id="$(docker compose ps -q "$service")"
    if [ -n "$container_id" ]; then
      container_state="$(docker inspect --format '{{.State.Status}}' "$container_id")"
      health_state="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")"

      if [ "$health_state" = "healthy" ]; then
        echo "[deploy] $service is healthy."
        return 0
      fi

      if [ "$container_state" = "exited" ] || [ "$container_state" = "dead" ]; then
        docker compose logs --tail 100 "$service" >&2
        return 1
      fi
    fi

    now="$(date +%s)"
    if [ $((now - start_time)) -ge "$timeout_seconds" ]; then
      echo "[deploy] Timed out waiting for $service health." >&2
      docker compose logs --tail 100 "$service" >&2
      return 1
    fi

    sleep 2
  done
}

verify_running_image() {
  service="$1"
  expected_image="$2"
  container_id="$(docker compose ps -q "$service")"

  if [ -z "$container_id" ]; then
    echo "[deploy] $service has no running container to verify." >&2
    return 1
  fi

  running_image_id="$(docker inspect --format '{{.Image}}' "$container_id")"
  expected_image_id="$(docker image inspect --format '{{.Id}}' "$expected_image")"
  if [ "$running_image_id" != "$expected_image_id" ]; then
    echo "[deploy] $service is not running the requested image $expected_image." >&2
    return 1
  fi

  echo "[deploy] $service runs $expected_image ($expected_image_id)."
}

rollback_on_failure() {
  exit_code="$?"
  if [ "$exit_code" -eq 0 ] || [ "$deployment_complete" = true ]; then
    return
  fi

  if [ "$migration_started" = true ]; then
    if [ "$schema_changed" = true ]; then
      echo "[deploy] Deploy failed after the enum schema cutover. Old application images will not be restored." >&2
    else
      echo "[deploy] Deploy failed while migrations were running; database revision is unknown. Old application images will not be restored." >&2
    fi
    echo "[deploy] Inspect with: docker compose run --rm --no-deps backend alembic current" >&2
    echo "[deploy] Recover with this revision or a newer schema-compatible image." >&2
    return
  fi

  if [ "$cutover_started" != true ] && [ "$application_replaced" != true ]; then
    echo "[deploy] Deploy failed before application replacement; current containers remain in place." >&2
    return
  fi

  if [ -n "$previous_backend_image" ] && [ -n "$previous_frontend_image" ]; then
    echo "[deploy] Deploy failed. Restoring prior application images." >&2
    if BACKEND_IMAGE="$previous_backend_image" FRONTEND_IMAGE="$previous_frontend_image" \
      docker compose up -d --no-deps --force-recreate backend frontend; then
      wait_for_health backend 120 || echo "[deploy] Prior backend did not recover cleanly." >&2
      wait_for_health frontend 120 || echo "[deploy] Prior frontend did not recover cleanly." >&2
    else
      echo "[deploy] Prior image pair could not be restarted automatically." >&2
    fi
  else
    echo "[deploy] Deploy failed before a prior image pair was available for rollback." >&2
  fi
}

trap rollback_on_failure EXIT

echo "[deploy] Pulling matching application images for $IMAGE_TAG."
docker compose pull backend frontend

echo "[deploy] Starting state services."
docker compose up -d db redis db-backup
wait_for_health db 120
if ! wait_for_health redis 30; then
  echo "[deploy] Redis is unavailable. Backend readiness must report degraded cache mode." >&2
fi

echo "[deploy] Preparing persistent asset permissions."
docker compose run --rm --no-deps static-init

echo "[deploy] Entering the migration maintenance window."
cutover_started=true
docker compose stop frontend
docker compose stop backend

echo "[deploy] Running the single migration owner."
docker compose run --rm --no-deps backend python3 /app/scripts/stamp_if_legacy.py
migration_started=true
docker compose run --rm --no-deps backend alembic upgrade head
schema_changed=true

echo "[deploy] Starting backend, then frontend."
application_replaced=true
docker compose up -d --no-deps --force-recreate backend
verify_running_image backend "$BACKEND_IMAGE"
wait_for_health backend 180
docker compose up -d --no-deps --force-recreate frontend
verify_running_image frontend "$FRONTEND_IMAGE"
wait_for_health frontend 180

echo "[deploy] Running routing smoke checks."
sh ./smoke.sh

deployment_complete=true
echo "[deploy] Revision $IMAGE_TAG is healthy."
