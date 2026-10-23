#!/usr/bin/env bash
# Apply services/legacy-billing/db/migrations/NNNN_*.sql in order.
#
# Connects with the standard libpq variables (PGHOST, PGPORT, PGDATABASE,
# PGUSER, PGPASSWORD, PGSSLMODE, PGSSLROOTCERT) as the billing owner role
# created by bootstrap/roles.sql. BILLING_APP_ROLE names the runtime role that
# 0006_app_grants.sql grants to.
#
# Each migration runs in its own transaction together with its row in
# billing_migrations.applied (version, name, sha256). Applied migrations are
# skipped; one whose file changed since it was applied stops the run. There is
# no reset or down path: to rebuild, drop and recreate the database.
#
# Run one instance at a time per database.
set -euo pipefail

: "${BILLING_APP_ROLE:?set BILLING_APP_ROLE to the runtime role that receives the grants}"

dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/migrations" && pwd)"
export PGOPTIONS="${PGOPTIONS:-} -c search_path=billing -c TimeZone=UTC"
psql_cmd=(psql -X -q -v ON_ERROR_STOP=1 -v app_role="$BILLING_APP_ROLE")

if [[ "$("${psql_cmd[@]}" -tA -c "SELECT rolsuper FROM pg_roles WHERE rolname = current_user")" == "t" \
      && "${BILLING_MIGRATE_ALLOW_SUPERUSER:-}" != "1" ]]; then
  echo "migrate.sh: refusing to run as a superuser; connect as the billing owner role" >&2
  echo "            (set BILLING_MIGRATE_ALLOW_SUPERUSER=1 to override)" >&2
  exit 2
fi

"${psql_cmd[@]}" <<'SQL'
CREATE SCHEMA IF NOT EXISTS billing_migrations;
CREATE TABLE IF NOT EXISTS billing_migrations.applied (
    version text PRIMARY KEY,
    name text NOT NULL,
    sha256 text NOT NULL,
    applied_by text NOT NULL DEFAULT current_user,
    applied_at timestamptz NOT NULL DEFAULT now()
);
SQL

shopt -s nullglob
files=("$dir"/[0-9][0-9][0-9][0-9]_*.sql)
if (( ${#files[@]} == 0 )); then
  echo "migrate.sh: no migrations found in $dir" >&2
  exit 1
fi

for file in "${files[@]}"; do
  name="$(basename "$file")"
  version="${name%%_*}"
  sha="$(sha256sum "$file" | cut -d' ' -f1)"
  recorded="$("${psql_cmd[@]}" -tA -v v="$version" <<'SQL'
SELECT sha256 FROM billing_migrations.applied WHERE version = :'v';
SQL
)"
  if [[ -n "$recorded" ]]; then
    if [[ "$recorded" != "$sha" ]]; then
      echo "migrate.sh: $name changed after it was applied (recorded $recorded, file $sha)" >&2
      exit 3
    fi
    echo "skip   $name"
    continue
  fi
  "${psql_cmd[@]}" --single-transaction -v v="$version" -v n="$name" -v s="$sha" -v f="$file" -f - <<'SQL'
\i :f
INSERT INTO billing_migrations.applied (version, name, sha256) VALUES (:'v', :'n', :'s');
SQL
  echo "apply  $name"
done
