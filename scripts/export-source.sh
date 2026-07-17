#!/bin/sh
set -eu

revision="$(git rev-parse --verify HEAD)"
output="${1:-keshepool-source-${revision}.tar.gz}"
case "$output" in
  /*) ;;
  *) output="$(pwd)/$output" ;;
esac

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT HUP INT TERM
stage="$work_dir/source"
mkdir -p "$stage"

allowlist="
backend/app
backend/alembic
backend/scripts
backend/tests
backend/Dockerfile
backend/entrypoint.sh
backend/alembic.ini
backend/requirements.txt
backend/requirements-dev.txt
frontend/src
frontend/public
frontend/scripts
frontend/Dockerfile
frontend/package.json
frontend/package-lock.json
frontend/next.config.ts
frontend/tsconfig.json
frontend/tsconfig.tests.json
frontend/eslint.config.mjs
frontend/postcss.config.mjs
.github/workflows
.gitleaks.toml
ops
scripts
docker-compose.yml
deploy.sh
smoke.sh
README.md
DEPLOYMENT.md
ADMIN_PRODUCT_MANUAL.md
"

git archive --format=tar HEAD $allowlist | tar -xf - -C "$stage"

find "$stage" -type f \( \
  -name '.env' -o -name '.env.*' -o \
  -iname '*.pem' -o -iname '*.key' -o -iname '*.crt' -o -iname '*.cer' -o -iname '*.p12' -o -iname '*.pfx' -o \
  -iname '*.sql' -o -iname '*.sql.gz' -o -iname '*.dump' -o -iname '*.backup' -o \
  -iname '*.tar' -o -iname '*.tar.gz' -o -iname '*.tgz' -o -iname '*.zip' -o \
  -iname '*token*.txt' -o -iname '*token*.json' \
\) -delete

if find "$stage" \( -name .git -o -name node_modules -o -name .next -o -name dist -o -name build -o -name backups \) -print -quit | grep -q .; then
  echo "source export blocked: forbidden directory entered staging" >&2
  exit 1
fi

tar -czf "$output" -C "$stage" .
echo "source export ready: $output"
