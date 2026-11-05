#!/usr/bin/env bash
# Write a fresh .env with a unique run-scoped project name and random local secrets. Never overwrites.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
umask 077
exec 9>"$ENV_FILE.lock"
flock 9
if [[ -f "$ENV_FILE" ]]; then echo "$ENV_FILE exists; leaving it alone" >&2; exit 0; fi
rnd() { python3 -c 'import secrets;print(secrets.token_hex(int(__import__("sys").argv[1])))' "$1"; }
project="${COMPOSE_PROJECT_NAME:-collection-$(rnd 4)}"
[[ "$project" =~ $PROJECT_RE ]] || die "COMPOSE_PROJECT_NAME must match $PROJECT_RE"
sed -e "s/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=$project/" \
    -e "s/^COLLECTION_PG_OWNER_PASSWORD=.*/COLLECTION_PG_OWNER_PASSWORD=$(rnd 24)/" \
    -e "s/^COLLECTION_PG_READER_PASSWORD=.*/COLLECTION_PG_READER_PASSWORD=$(rnd 24)/" \
    -e "s/^COLLECTION_GRAFANA_ADMIN_PASSWORD=.*/COLLECTION_GRAFANA_ADMIN_PASSWORD=$(rnd 24)/" \
    -e "s/^COLLECTION_ACCESS_TOKEN=.*/COLLECTION_ACCESS_TOKEN=$(rnd 24)/" \
    "$COLLECTION_DIR/.env.example" > "$ENV_FILE.tmp"
mv "$ENV_FILE.tmp" "$ENV_FILE"
echo "wrote $ENV_FILE (project $project)" >&2
