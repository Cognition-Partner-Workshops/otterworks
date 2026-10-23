#!/usr/bin/env bash
# Builds the billing schema with the migration runner, then loads the test seed.
# Runs as billing_owner over the libpq environment (verify-full TLS in the
# migrated Compose stack). With BILLING_REBUILD_RESET=1 it first drops the two
# schemas the owner created, so every parity scenario starts from a fresh
# db/migrate.sh run instead of from schema.sql.
set -euo pipefail

db_dir=/work/db
psql_cmd=(psql -X -q -v ON_ERROR_STOP=1)

if [[ "${BILLING_REBUILD_RESET:-0}" == 1 ]]; then
  "${psql_cmd[@]}" <<'SQL'
DROP SCHEMA IF EXISTS billing CASCADE;
DROP SCHEMA IF EXISTS billing_migrations CASCADE;
SQL
fi

bash "$db_dir/migrate.sh"
"${psql_cmd[@]}" -f "$db_dir/seed.sql"
"${psql_cmd[@]}" -tA <<'SQL'
SELECT 'rebuilt as ' || current_user || ' ssl=' || ssl || ' migrations=' ||
       (SELECT string_agg(version, ',' ORDER BY version) FROM billing_migrations.applied)
FROM pg_stat_ssl WHERE pid = pg_backend_pid();
SQL
