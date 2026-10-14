#!/usr/bin/env bash
# Local stand-in for the legacy billing PostgreSQL (the Compose "before state" in
# docker-compose.procs.yml), plus the SELECT-only role the migration run connects as
# (legacy_billing_ro.sql). Starts only the database service; nothing here touches a
# shared or customer system.
#
#   NS=mig PROCS_DB_PORT=55433 .migration/fixtures/legacy_billing_source.sh
#
# The role password comes from BILLING_RO_PASSWORD, or from the "password" field of the
# OW_BILLING_PG_RO_DSN secret (JSON, see profiles/postgresql.md):
#   {"user":"billing_ro","password":"<secret>","host":"127.0.0.1","port":<PROCS_DB_PORT>,"database":"billing_<NS>","schema":"billing"}
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
NS="${NS:-mig}"
PROCS_DB_PORT="${PROCS_DB_PORT:-55433}"
if [ -z "${BILLING_RO_PASSWORD:-}" ] && [ -n "${OW_BILLING_PG_RO_DSN:-}" ]; then
  BILLING_RO_PASSWORD="$(python3 -c 'import json, os; print(json.loads(os.environ["OW_BILLING_PG_RO_DSN"])["password"])')"
fi
if [ -z "${BILLING_RO_PASSWORD:-}" ]; then
  echo "set BILLING_RO_PASSWORD or OW_BILLING_PG_RO_DSN (never commit the value)" >&2
  exit 1
fi
export NS PROCS_DB_PORT RO_PW="$BILLING_RO_PASSWORD"
docker compose -p "otterworks-procs-${NS}" -f docker-compose.procs.yml up -d --wait legacy-billing-db
docker compose -p "otterworks-procs-${NS}" -f docker-compose.procs.yml exec -T -e RO_PW legacy-billing-db \
  psql -v ON_ERROR_STOP=1 -U billing -d "billing_${NS}" -f - < .migration/fixtures/legacy_billing_ro.sql
echo "legacy_billing_source: billing_${NS} on 127.0.0.1:${PROCS_DB_PORT}; role billing_ro = SELECT only"
