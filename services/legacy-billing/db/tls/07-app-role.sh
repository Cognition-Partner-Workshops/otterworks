#!/usr/bin/env bash
set -euo pipefail

app_password="${BILLING_APP_PASSWORD:-billing_app}"
psql -X -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v owner_role=billing_owner \
  -v app_role=billing_app \
  -f /docker-entrypoint-initdb.d/07-roles.sql.source
psql -X -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v app_role=billing_app \
  -f /docker-entrypoint-initdb.d/07-app-grants.sql.source
psql -X -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v app_role=billing_app \
  -v app_password="$app_password" <<'SQL'
ALTER ROLE :"app_role" PASSWORD :'app_password';
SQL

pg_hba_tmp="$(mktemp "$PGDATA/pg_hba.conf.XXXXXX")"
{
  printf '%s\n' \
    'hostssl all billing_app all scram-sha-256' \
    'host all billing_app all reject'
  cat "$PGDATA/pg_hba.conf"
} > "$pg_hba_tmp"
mv "$pg_hba_tmp" "$PGDATA/pg_hba.conf"
chmod 0600 "$PGDATA/pg_hba.conf"
