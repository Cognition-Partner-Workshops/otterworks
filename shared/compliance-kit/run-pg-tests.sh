#!/usr/bin/env bash
# Run the PostgreSQL half of the compliance kit against a throwaway
# PostgreSQL 16 container, then remove the container.
set -euo pipefail
cd "$(dirname "$0")/postgres"
NAME="compliance-kit-pg-$$"
IMAGE="${PG_IMAGE:-postgres:16}"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$NAME" -e POSTGRES_PASSWORD=kit "$IMAGE" >/dev/null
for _ in $(seq 1 60); do
  docker exec "$NAME" pg_isready -U postgres -q 2>/dev/null && break
  sleep 1
done
sleep 1
for f in 01_masking.sql 02_audit.sql 03_retention.sql tests/test_kit.sql; do
  docker exec -i -e PGOPTIONS="-c client_min_messages=warning" "$NAME" psql -X -q -v ON_ERROR_STOP=1 -U postgres -d postgres < "$f"
done
