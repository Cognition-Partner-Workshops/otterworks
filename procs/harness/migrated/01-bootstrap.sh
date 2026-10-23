#!/usr/bin/env bash
# initdb hook for docker-compose.procs.migrated.yml. Models a managed instance:
# the image superuser only creates platform_admin (CREATEROLE, not superuser)
# and the billing database it owns; platform_admin then runs
# services/legacy-billing/db/bootstrap/roles.sql. The billing schema itself is
# created later by db/migrate.sh as billing_owner (see rebuild.sh).
set -euo pipefail

psql -X -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v db="$BILLING_DB" -v platform_password="$PLATFORM_ADMIN_PASSWORD" <<'SQL'
CREATE ROLE platform_admin LOGIN CREATEROLE NOSUPERUSER PASSWORD :'platform_password';
CREATE DATABASE :"db" OWNER platform_admin;
SQL

psql -X -v ON_ERROR_STOP=1 --username platform_admin --dbname "$BILLING_DB" \
  -v owner_role=billing_owner -v app_role=billing_app \
  -f /bootstrap/roles.sql

psql -X -v ON_ERROR_STOP=1 --username platform_admin --dbname "$BILLING_DB" \
  -v owner_password="$BILLING_OWNER_PASSWORD" -v app_password="$BILLING_APP_PASSWORD" <<'SQL'
ALTER ROLE billing_owner PASSWORD :'owner_password';
ALTER ROLE billing_app PASSWORD :'app_password';
SQL

# Billing roles may only connect over TLS, as on a managed instance.
pg_hba_tmp="$(mktemp "$PGDATA/pg_hba.conf.XXXXXX")"
{
  printf '%s\n' \
    'hostssl all platform_admin,billing_owner,billing_app all scram-sha-256' \
    'host all platform_admin,billing_owner,billing_app all reject'
  cat "$PGDATA/pg_hba.conf"
} > "$pg_hba_tmp"
mv "$pg_hba_tmp" "$PGDATA/pg_hba.conf"
chmod 0600 "$PGDATA/pg_hba.conf"
