#!/usr/bin/env bash
set -euo pipefail

db_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

announce() {
  printf '\n==> %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

random_password() {
  od -An -N24 -tx1 /dev/urandom | tr -d ' \n'
}

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is required"
fi
if ! docker image inspect postgres:16 >/dev/null 2>&1; then
  fail "local postgres:16 image is required; the verifier does not pull images"
fi

postgres_password="$(random_password)"
platform_password="$(random_password)"
owner_password="$(random_password)"
app_password="$(random_password)"
nobody_password="$(random_password)"
container_id=''
reference_file=''
migration_file=''

cleanup() {
  if [[ -n "$container_id" ]]; then
    docker rm -f "$container_id" >/dev/null 2>&1 || true
    printf 'Removed throwaway PostgreSQL container.\n'
    container_id=''
  fi
  [[ -z "$reference_file" ]] || rm -f "$reference_file"
  [[ -z "$migration_file" ]] || rm -f "$migration_file"
}
trap cleanup EXIT

announce "Start isolated postgres:16 on a random loopback port"
container_id="$(
  docker run -d --rm \
    --name "billing-migration-verify-$$" \
    -e POSTGRES_PASSWORD="$postgres_password" \
    -p 127.0.0.1::5432 \
    -v "$db_dir:/work/db:ro" \
    postgres:16
)"
port_mapping="$(docker port "$container_id" 5432/tcp | head -n 1)"
host_port="${port_mapping##*:}"
printf 'Container: %s\nMapped port: 127.0.0.1:%s -> 5432/tcp\n' \
  "$container_id" "$host_port"

if command -v psql >/dev/null 2>&1; then
  psql_mode=host
  file_prefix="$db_dir"
  printf 'Using host psql over the published TCP port.\n'
else
  psql_mode=container
  file_prefix=/work/db
  printf 'Host psql not found; using container psql over 127.0.0.1 TCP.\n'
fi

psql_exec() {
  local role="$1"
  local database="$2"
  local password="$3"
  shift 3

  if [[ "$psql_mode" == host ]]; then
    PGPASSWORD="$password" PGHOST=127.0.0.1 PGPORT="$host_port" \
      PGUSER="$role" PGDATABASE="$database" PGOPTIONS='' \
      psql -X -v ON_ERROR_STOP=1 -P pager=off "$@"
  else
    docker exec -i \
      -e PGHOST=127.0.0.1 \
      -e PGPORT=5432 \
      -e PGUSER="$role" \
      -e PGDATABASE="$database" \
      -e PGPASSWORD="$password" \
      -e PGOPTIONS= \
      "$container_id" psql -X -v ON_ERROR_STOP=1 -P pager=off "$@"
  fi
}

run_migrate() {
  local role="$1"
  local password="$2"

  if [[ "$psql_mode" == host ]]; then
    env -u PGOPTIONS \
      PGHOST=127.0.0.1 PGPORT="$host_port" PGDATABASE=billing_mig \
      PGUSER="$role" PGPASSWORD="$password" BILLING_APP_ROLE=billing_app \
      bash "$db_dir/migrate.sh"
  else
    docker exec -i \
      -e PGHOST=127.0.0.1 \
      -e PGPORT=5432 \
      -e PGDATABASE=billing_mig \
      -e PGUSER="$role" \
      -e PGPASSWORD="$password" \
      -e PGOPTIONS= \
      -e BILLING_APP_ROLE=billing_app \
      "$container_id" bash /work/db/migrate.sh
  fi
}

announce "Wait for PostgreSQL readiness"
ready=0
for _ in {1..60}; do
  if docker exec \
    -e PGPASSWORD="$postgres_password" \
    "$container_id" pg_isready -h 127.0.0.1 -U postgres -d postgres \
    >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
[[ "$ready" == 1 ]] || fail "PostgreSQL did not become ready within 60 seconds"
docker exec \
  -e PGPASSWORD="$postgres_password" \
  "$container_id" pg_isready -h 127.0.0.1 -U postgres -d postgres

announce "As postgres only, create platform_admin and the two test databases"
psql_exec postgres postgres "$postgres_password" \
  -v platform_password="$platform_password" \
  <<'SQL'
CREATE ROLE platform_admin LOGIN CREATEROLE NOSUPERUSER PASSWORD :'platform_password';
SQL
psql_exec postgres postgres "$postgres_password" \
  -c "CREATE DATABASE billing_mig OWNER platform_admin"
psql_exec postgres postgres "$postgres_password" \
  -c "CREATE DATABASE billing_ref OWNER platform_admin"

announce "As platform_admin, bootstrap billing roles and set test passwords"
psql_exec platform_admin billing_mig "$platform_password" \
  -v owner_role=billing_owner \
  -v app_role=billing_app \
  -f "$file_prefix/bootstrap/roles.sql"
psql_exec platform_admin billing_mig "$platform_password" \
  -v owner_role=billing_owner \
  -v app_role=billing_app \
  -v owner_password="$owner_password" \
  -v app_password="$app_password" <<'SQL'
ALTER ROLE :"owner_role" PASSWORD :'owner_password';
ALTER ROLE :"app_role" PASSWORD :'app_password';
SELECT rolname, rolsuper, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname IN (:'owner_role', :'app_role')
ORDER BY rolname;
SQL

announce "As billing_owner, apply migrations 0001 through 0006"
run_migrate billing_owner "$owner_password"

announce "As billing_owner, rerun migrations and confirm all are skipped"
run_migrate billing_owner "$owner_password"

announce "Inspect the applied migration checksums"
psql_exec billing_owner billing_mig "$owner_password" \
  -c "SELECT * FROM billing_migrations.applied ORDER BY version"

announce "Assert schema objects, ownership, extensions, and non-superuser identity"
psql_exec billing_owner billing_mig "$owner_password" <<'SQL'
SELECT current_user, r.rolsuper
FROM pg_roles AS r
WHERE r.rolname = current_user;
SELECT count(*) AS billing_tables
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'billing' AND c.relkind IN ('r', 'p');
SELECT count(*) AS routines,
       count(*) FILTER (WHERE p.prokind = 'f') AS functions,
       count(*) FILTER (WHERE p.prokind = 'p') AS procedures
FROM pg_proc AS p
JOIN pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'billing';
SELECT extname FROM pg_extension ORDER BY extname;

DO $assertions$
DECLARE
    table_count integer;
    routine_count integer;
    function_count integer;
    procedure_count integer;
    extension_count integer;
    wrong_table_owners integer;
    wrong_routine_owners integer;
    is_super boolean;
BEGIN
    SELECT count(*) INTO table_count
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'billing' AND c.relkind IN ('r', 'p');

    SELECT count(*),
           count(*) FILTER (WHERE p.prokind = 'f'),
           count(*) FILTER (WHERE p.prokind = 'p')
      INTO routine_count, function_count, procedure_count
    FROM pg_proc AS p
    JOIN pg_namespace AS n ON n.oid = p.pronamespace
    WHERE n.nspname = 'billing';

    SELECT count(*) INTO wrong_table_owners
    FROM pg_class AS c
    JOIN pg_namespace AS n ON n.oid = c.relnamespace
    WHERE n.nspname = 'billing'
      AND c.relkind IN ('r', 'p')
      AND c.relowner <> current_user::regrole;

    SELECT count(*) INTO wrong_routine_owners
    FROM pg_proc AS p
    JOIN pg_namespace AS n ON n.oid = p.pronamespace
    WHERE n.nspname = 'billing'
      AND p.proowner <> current_user::regrole;

    SELECT count(*) INTO extension_count FROM pg_extension;
    SELECT rolsuper INTO is_super FROM pg_roles WHERE rolname = current_user;

    IF table_count <> 11 THEN
        RAISE EXCEPTION 'expected 11 billing tables, found %', table_count;
    END IF;
    IF routine_count <> 12 OR function_count <> 7 OR procedure_count <> 5 THEN
        RAISE EXCEPTION 'expected 12 routines (7 functions, 5 procedures), found % (% functions, % procedures)',
            routine_count, function_count, procedure_count;
    END IF;
    IF (SELECT nspowner FROM pg_namespace WHERE nspname = 'billing')
       <> current_user::regrole THEN
        RAISE EXCEPTION 'billing schema is not owned by current_user';
    END IF;
    IF wrong_table_owners <> 0 OR wrong_routine_owners <> 0 THEN
        RAISE EXCEPTION 'billing tables/routines have owners other than current_user';
    END IF;
    IF extension_count <> 1 OR NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'plpgsql'
    ) THEN
        RAISE EXCEPTION 'expected plpgsql to be the only extension';
    END IF;
    IF is_super IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'current_user must not be a superuser';
    END IF;
END
$assertions$;
SQL

announce "Compare routine definitions against the original source files"
for pair in \
  '0001_billing_schema.sql schema.sql' \
  '0002_plans.sql procs/plans.sql' \
  '0003_rating.sql procs/rating.sql' \
  '0004_invoicing.sql procs/invoicing.sql' \
  '0005_dunning.sql procs/dunning.sql'; do
  read -r migration source <<<"$pair"
  cmp "$db_dir/migrations/$migration" "$db_dir/$source"
  printf 'cmp PASS: migrations/%s matches %s\n' "$migration" "$source"
done

for source in \
  schema.sql \
  procs/plans.sql \
  procs/rating.sql \
  procs/invoicing.sql \
  procs/dunning.sql; do
  printf 'Load reference source: %s\n' "$source"
  psql_exec platform_admin billing_ref "$platform_password" \
    -f "$file_prefix/$source"
done

routine_query="SELECT p.proname, p.prokind,
       pg_get_function_identity_arguments(p.oid), md5(p.prosrc),
       p.prosecdef, p.proconfig
FROM pg_proc AS p
JOIN pg_namespace AS n ON n.oid = p.pronamespace
WHERE n.nspname = 'billing'
ORDER BY 1, 3"
reference_file="$(mktemp)"
migration_file="$(mktemp)"
psql_exec platform_admin billing_ref "$platform_password" \
  -A -t -F '|' -P null='[NULL]' -c "$routine_query" >"$reference_file"
psql_exec billing_owner billing_mig "$owner_password" \
  -A -t -F '|' -P null='[NULL]' -c "$routine_query" >"$migration_file"
printf '\n-- billing_ref routine fingerprints --\n'
cat "$reference_file"
printf '\n-- billing_mig routine fingerprints --\n'
cat "$migration_file"
printf '\n-- fingerprint diff (no output means identical) --\n'
diff -u "$reference_file" "$migration_file"

announce "Load seed.sql as billing_owner (test data only)"
psql_exec billing_owner billing_mig "$owner_password" \
  -f "$file_prefix/seed.sql"

announce "As billing_app, verify role settings without PGOPTIONS"
psql_exec billing_app billing_mig "$app_password" <<'SQL'
SHOW search_path;
SHOW TimeZone;
SQL

announce "As billing_app, smoke-test plans and entitlement"
psql_exec billing_app billing_mig "$app_password" <<'SQL'
SELECT count(*) AS active_plans FROM billing.fn_list_plans();
DO $assertion$
BEGIN
    IF (SELECT count(*) FROM billing.fn_list_plans()) <> 3 THEN
        RAISE EXCEPTION 'expected 3 active plans';
    END IF;
END
$assertion$;
SELECT * FROM billing.fn_entitlement(
    '00000000-0000-0000-0000-000000000004',
    '2026-07-15'
);
SQL

announce "As billing_app, smoke-test rating, invoice preview, and invoice issue"
psql_exec billing_app billing_mig "$app_password" <<'SQL'
SELECT * FROM billing.fn_usage_rating(
    '00000000-0000-0000-0000-000000000004',
    '2026-07-01',
    '2026-07-31'
);
SELECT * FROM billing.fn_invoice_preview(
    '00000000-0000-0000-0000-000000000004',
    '2026-07-01',
    '2026-07-31'
);
CALL billing.sp_issue_invoice(
    '00000000-0000-0000-0000-000000000004',
    '2026-07-01',
    '2026-07-31'
);
SELECT id AS issued_invoice_id
FROM billing.invoices
WHERE tenant_id = '00000000-0000-0000-0000-000000000004'
  AND issued_at::date = DATE '2026-07-31'
ORDER BY id;
SELECT * FROM billing.fn_invoice_lines((
    SELECT id
    FROM billing.invoices
    WHERE tenant_id = '00000000-0000-0000-0000-000000000004'
      AND issued_at::date = DATE '2026-07-31'
    ORDER BY id
    LIMIT 1
));
DO $assertion$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM billing.invoices AS i
        JOIN billing.invoice_lines AS l ON l.invoice_id = i.id
        WHERE i.tenant_id = '00000000-0000-0000-0000-000000000004'
          AND i.issued_at::date = DATE '2026-07-31'
    ) THEN
        RAISE EXCEPTION 'invoice issue did not produce invoice lines';
    END IF;
END
$assertion$;
SQL

announce "As billing_app, smoke-test plan change and dunning routines"
psql_exec billing_app billing_mig "$app_password" <<'SQL'
CALL billing.sp_change_plan(
    '00000000-0000-0000-0000-000000000004',
    '10000000-0000-0000-0000-000000000002',
    '2026-08-01'
);
SELECT * FROM billing.fn_overdue_accounts('2026-03-07');
CALL billing.sp_schedule_dunning('2026-03-07');
CALL billing.sp_suspend_overdue('2026-03-07');
SQL

expect_permission_denied() {
  local label="$1"
  local role="$2"
  local password="$3"
  local sql="$4"
  local output
  local status

  printf '\nExpected permission denial: %s\n' "$label"
  if output="$(psql_exec "$role" billing_mig "$password" -c "$sql" 2>&1)"; then
    printf '%s\n' "$output"
    fail "$label unexpectedly succeeded"
  else
    status=$?
  fi
  printf '%s\n' "$output"
  if [[ "$output" != *"permission denied"* ]]; then
    fail "$label failed without a permission-denied error (status $status)"
  fi
  printf 'Confirmed expected permission-denied failure (status %s).\n' "$status"
}

announce "Assert billing_app cannot create, delete, or truncate"
expect_permission_denied \
  "CREATE TABLE billing.x(i int)" \
  billing_app "$app_password" \
  "CREATE TABLE billing.x(i int)"
expect_permission_denied \
  "DELETE FROM billing.tenants" \
  billing_app "$app_password" \
  "DELETE FROM billing.tenants"
expect_permission_denied \
  "TRUNCATE billing.usage_events" \
  billing_app "$app_password" \
  "TRUNCATE billing.usage_events"

announce "Create nobody_role as platform_admin and verify no billing access"
psql_exec platform_admin billing_mig "$platform_password" \
  -v nobody_password="$nobody_password" <<'SQL'
CREATE ROLE nobody_role LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT PASSWORD :'nobody_password';
GRANT CONNECT ON DATABASE :"DBNAME" TO nobody_role;
SQL
expect_permission_denied \
  "nobody_role SELECT from billing.fn_list_plans()" \
  nobody_role "$nobody_password" \
  "SELECT * FROM billing.fn_list_plans()"

announce "Tamper with migration 0003 and assert checksum drift is rejected"
original_sha="$(
  psql_exec billing_owner billing_mig "$owner_password" \
    -A -t -c "SELECT sha256 FROM billing_migrations.applied WHERE version = '0003'"
)"
[[ -n "$original_sha" ]] || fail "could not read the original checksum for migration 0003"
psql_exec billing_owner billing_mig "$owner_password" \
  -c "UPDATE billing_migrations.applied SET sha256 = 'x' WHERE version = '0003'"
if tamper_output="$(run_migrate billing_owner "$owner_password" 2>&1)"; then
  printf '%s\n' "$tamper_output"
  fail "migrate.sh accepted a changed checksum for migration 0003"
else
  tamper_status=$?
fi
printf '%s\n' "$tamper_output"
[[ "$tamper_output" == *"changed after it was applied"* ]] ||
  fail "tamper run failed without the changed-after-applied message (status $tamper_status)"
psql_exec billing_owner billing_mig "$owner_password" \
  -v original_sha="$original_sha" \
  <<'SQL'
UPDATE billing_migrations.applied
SET sha256 = :'original_sha'
WHERE version = '0003';
SQL
printf 'Tamper check rejected the file checksum and restored the row.\n'

announce "Assert migrate.sh refuses a superuser with exit status 2"
if superuser_output="$(run_migrate postgres "$postgres_password" 2>&1)"; then
  printf '%s\n' "$superuser_output"
  fail "migrate.sh unexpectedly accepted a superuser"
else
  superuser_status=$?
fi
printf '%s\n' "$superuser_output"
[[ "$superuser_status" == 2 ]] ||
  fail "superuser run exited $superuser_status instead of 2"
[[ "$superuser_output" == *"refusing to run as a superuser"* ]] ||
  fail "superuser run did not print the refusal message"

cleanup
printf '\ng-migrate-clean: PASS\n'
