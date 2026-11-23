#!/usr/bin/env bash
# Gives the local compose stack a per-machine Postgres password in the untracked
# .env, which compose reads for ${POSTGRES_PASSWORD}. Idempotent: an existing
# password is kept. When a Postgres volume from before this file existed is
# found, its role is moved to the new password so the stack keeps working.
set -euo pipefail
cd "$(dirname "$0")/.."

envFile=.env
if [ -f "$envFile" ] && grep -q '^POSTGRES_PASSWORD=.' "$envFile"; then
  exit 0
fi

password="$(openssl rand -hex 24)"
touch "$envFile"
chmod 600 "$envFile"
printf 'POSTGRES_PASSWORD=%s\n' "$password" >> "$envFile"
echo "dev-env: wrote a new local POSTGRES_PASSWORD to $envFile"

project="${COMPOSE_PROJECT_NAME:-$(basename "$PWD")}"
if docker volume inspect "${project}_postgres_data" >/dev/null 2>&1; then
  echo "dev-env: existing Postgres volume ${project}_postgres_data; setting role otterworks to the new password"
  docker compose -f docker-compose.infra.yml up -d postgres
  for _ in $(seq 1 30); do
    docker exec otterworks-postgres pg_isready -q -U otterworks && break
    sleep 1
  done
  docker exec -i otterworks-postgres psql -q -v ON_ERROR_STOP=1 -U otterworks -d otterworks \
    -v pw="$password" <<< "ALTER ROLE otterworks PASSWORD :'pw';"
fi
