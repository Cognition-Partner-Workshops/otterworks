#!/usr/bin/env bash
# Local stand-in for the legacy billing PostgreSQL (the Compose "before state" in
# docker-compose.procs.yml), plus the SELECT-only role the migration run connects as.
# Starts only the database service; nothing here touches a shared or customer system.
#
#   NS=mig PROCS_DB_PORT=55433 .migration/fixtures/legacy_billing_source.sh
#
# Afterwards store POSTGRESQL_RO_DSN (JSON, see profiles/postgresql.md) as:
#   {"user":"billing_ro","password":"<BILLING_RO_PASSWORD>","host":"127.0.0.1","port":<PROCS_DB_PORT>,"database":"billing_<NS>","schema":"billing"}
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
: "${NS:=mig}"
: "${PROCS_DB_PORT:=55433}"
: "${BILLING_RO_PASSWORD:?set BILLING_RO_PASSWORD (the value goes into the POSTGRESQL_RO_DSN secret, never into git)}"
export NS PROCS_DB_PORT
docker compose -p "otterworks-procs-${NS}" -f docker-compose.procs.yml up -d --wait legacy-billing-db
docker compose -p "otterworks-procs-${NS}" -f docker-compose.procs.yml exec -T \
  -e RO_PW="${BILLING_RO_PASSWORD}" legacy-billing-db \
  psql -v ON_ERROR_STOP=1 -U billing -d "billing_${NS}" <<'SQL'
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'billing_ro') THEN
    CREATE ROLE billing_ro LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
  END IF;
END $$;
SQL
docker compose -p "otterworks-procs-${NS}" -f docker-compose.procs.yml exec -T legacy-billing-db \
  sh -c 'psql -v ON_ERROR_STOP=1 -U billing -d "$POSTGRES_DB" -c "ALTER ROLE billing_ro PASSWORD '"'"'$0'"'"'"' "${BILLING_RO_PASSWORD}"
docker compose -p "otterworks-procs-${NS}" -f docker-compose.procs.yml exec -T legacy-billing-db \
  psql -v ON_ERROR_STOP=1 -U billing -d "billing_${NS}" <<'SQL'
REVOKE ALL ON SCHEMA billing FROM billing_ro;
GRANT USAGE ON SCHEMA billing TO billing_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA billing TO billing_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE billing IN SCHEMA billing GRANT SELECT ON TABLES TO billing_ro;
SQL
echo "legacy_billing_source: billing_${NS} on 127.0.0.1:${PROCS_DB_PORT}; role billing_ro = SELECT only"
