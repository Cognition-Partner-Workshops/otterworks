#!/usr/bin/env bash
# Integration test for per-tenant Postgres logins (scripts/lib/tenant-common.sh).
#
# Runs the exact provisioning / drop / orphan-role SQL the deploy, teardown and
# reaper Jobs run, against a throwaway local Postgres (and PgBouncer) in Docker.
# The "master" login here is a NOSUPERUSER CREATEDB CREATEROLE role, which is
# what the RDS master user is. Nothing outside this machine is touched.
#
#   ./scripts/tests/test-tenant-db-isolation.sh
#   PG_IMAGE=postgres:16-alpine ./scripts/tests/test-tenant-db-isolation.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/tenant-common.sh
source "${HERE}/../lib/tenant-common.sh"

PG_IMAGE="${PG_IMAGE:-postgres:15-alpine}"   # RDS runs 15.x
PGB_IMAGE="${PGB_IMAGE:-edoburu/pgbouncer:v1.25.2-p0}"
RUN_ID="tdbi-$$"
NET="${RUN_ID}"; PG="${RUN_ID}-pg"; PGB="${RUN_ID}-pgb"
WORK="$(mktemp -d)"
ADMIN="otterworks_admin"

cleanup() {
  docker rm -f "${PG}" "${PGB}" >/dev/null 2>&1 || true
  docker network rm "${NET}" >/dev/null 2>&1 || true
  rm -rf "${WORK}"
}
trap cleanup EXIT

FAILS=0; PASSES=0
pass() { PASSES=$((PASSES + 1)); printf '  ok   %s\n' "$1"; }
fail() { FAILS=$((FAILS + 1)); printf '  FAIL %s\n' "$1"; }

# Passwords stay in the environment: docker exec -e NAME copies the value from
# this process's env, so none of them appears on an argv.
SUPER_PW="$(gen_db_password)"; ADMIN_PW="$(gen_db_password)"
export SUPER_PW ADMIN_PW

# Run SQL from stdin as the master login. Extra env names are forwarded as-is.
as_admin() {
  local db="${1:-otterworks}"; shift || true
  local envs=(-e "PGPASSWORD")
  for e in "$@"; do envs+=(-e "$e"); done
  PGPASSWORD="${ADMIN_PW}" docker exec -i "${envs[@]}" "${PG}" \
    psql "host=127.0.0.1 dbname=${db} user=${ADMIN}" -X -q -tA -v ON_ERROR_STOP=1 -f -
}

# One unaligned value from the master login: admin_value <db> <sql>
admin_value() { printf '%s\n' "$2" | as_admin "$1" 2>&1 | sed '/^$/d'; }

# psql as a tenant login: tenant_psql <user> <password> <db> <sql> [port] [host]
tenant_psql() {
  local user="$1" pw="$2" db="$3" sql="$4" port="${5:-5432}" host="${6:-${PG}}"
  PGPASSWORD="${pw}" docker run --rm -i --network "${NET}" -e PGPASSWORD "${PG_IMAGE}" \
    psql "host=${host} port=${port} dbname=${db} user=${user} sslmode=disable connect_timeout=5" \
         -X -q -tA -v ON_ERROR_STOP=1 -c "${sql}" 2>&1
}

expect_ok() {   # desc expected-output cmd...
  local desc="$1" want="$2" out; shift 2
  if out="$("$@")" && { [ -z "${want}" ] || [ "${out}" = "${want}" ]; }; then pass "${desc}"
  else fail "${desc} (got: $(printf '%s' "${out}" | tail -1))"; fi
}
expect_denied() {   # desc error-regex cmd...
  local desc="$1" re="$2" out; shift 2
  if out="$("$@")"; then fail "${desc} (unexpectedly succeeded: ${out})"
  elif printf '%s' "${out}" | grep -Eq "${re}"; then pass "${desc}"
  else fail "${desc} (wrong error: $(printf '%s' "${out}" | tail -1))"; fi
}

provision() {   # tenant-id password
  local db role; db="$(tenant_db_name "$1")"; role="$(tenant_db_role "${db}")"
  tenant_db_provision_sql "${db}" "${role}" | TENANT_DB_PASSWORD="$2" as_admin otterworks TENANT_DB_PASSWORD
}

echo "== starting ${PG_IMAGE}"
docker network create "${NET}" >/dev/null
docker run -d --name "${PG}" --network "${NET}" -e POSTGRES_PASSWORD="${SUPER_PW}" "${PG_IMAGE}" >/dev/null
for _ in $(seq 1 60); do
  PGPASSWORD="${SUPER_PW}" docker exec -e PGPASSWORD "${PG}" psql -h 127.0.0.1 -U postgres -tAc 'select 1' >/dev/null 2>&1 && break
  sleep 1
done
# Emulate RDS: the master login is not a superuser.
PGPASSWORD="${SUPER_PW}" docker exec -i -e PGPASSWORD -e ADMIN_PW "${PG}" \
  psql -h 127.0.0.1 -U postgres -X -q -v ON_ERROR_STOP=1 -f - >/dev/null <<'SQL'
\getenv admin_pw ADMIN_PW
CREATE ROLE otterworks_admin LOGIN CREATEDB CREATEROLE PASSWORD :'admin_pw';
CREATE DATABASE otterworks OWNER otterworks_admin;
SQL

echo "== legacy tenant (pre-fix layout: everything owned by the master login)"
as_admin otterworks >/dev/null <<'SQL'
CREATE DATABASE otterworks_legacy;
\connect otterworks_legacy
CREATE TABLE users (id serial PRIMARY KEY, email text);
INSERT INTO users (email) VALUES ('a@example.test');
CREATE SCHEMA analytics;
CREATE TABLE analytics.events (id bigint GENERATED ALWAYS AS IDENTITY, name text);
CREATE SEQUENCE free_seq;
CREATE VIEW user_emails AS SELECT email FROM users;
CREATE TYPE mood AS ENUM ('ok', 'meh');
CREATE FUNCTION one() RETURNS int LANGUAGE sql AS 'SELECT 1';
SQL

PW_A="$(gen_db_password)"; PW_B="$(gen_db_password)"; PW_L="$(gen_db_password)"; PW_C="$(gen_db_password)"
echo "== provisioning tenants a, b, legacy, c"
for t in "a:${PW_A}" "b:${PW_B}" "legacy:${PW_L}" "c:${PW_C}"; do provision "${t%%:*}" "${t#*:}"; done
provision a "${PW_A}" && pass "provisioning is idempotent (re-run for a)"
provision_empty_pw() {
  tenant_db_provision_sql otterworks_x otterworks_x_app | TENANT_DB_PASSWORD="" as_admin otterworks TENANT_DB_PASSWORD 2>&1
}
expect_denied "provisioning refuses an empty tenant password" "missing or too short" provision_empty_pw

A=otterworks_a_app; B=otterworks_b_app; L=otterworks_legacy_app
echo "== isolation (direct to Postgres)"
expect_ok     "a connects to its own database as ${A}" "${A}" tenant_psql "${A}" "${PW_A}" otterworks_a "select current_user"
expect_ok     "a can run DDL/DML in its own database" "1" \
  tenant_psql "${A}" "${PW_A}" otterworks_a "create table t(x int); insert into t values (1); select count(*) from t"
expect_ok     "search_path default survives (public, analytics)" "public, analytics" \
  tenant_psql "${A}" "${PW_A}" otterworks_a "show search_path"
expect_denied "a cannot connect to tenant b's database" "permission denied for database" \
  tenant_psql "${A}" "${PW_A}" otterworks_b "select 1"
expect_denied "a cannot connect to the legacy tenant's database" "permission denied for database" \
  tenant_psql "${A}" "${PW_A}" otterworks_legacy "select 1"
expect_denied "a cannot connect to the bootstrap otterworks database" "permission denied for database" \
  tenant_psql "${A}" "${PW_A}" otterworks "select 1"
expect_denied "a cannot log in with b's password" "password authentication failed" \
  tenant_psql "${A}" "${PW_B}" otterworks_a "select 1"
expect_denied "a cannot CREATE DATABASE" "permission denied to create database" \
  tenant_psql "${A}" "${PW_A}" otterworks_a "create database evil"
expect_denied "a cannot CREATE ROLE" "permission denied to create role" \
  tenant_psql "${A}" "${PW_A}" otterworks_a "create role evil"
expect_denied "a cannot DROP tenant b's database" "must be owner of database" \
  tenant_psql "${A}" "${PW_A}" otterworks_a "drop database otterworks_b"
expect_denied "a cannot assume the master login" "permission denied to set role" \
  tenant_psql "${A}" "${PW_A}" otterworks_a "set role ${ADMIN}"
expect_ok     "a holds no superuser/createdb/createrole, capped at 30 connections" "f|f|f|30" \
  tenant_psql "${A}" "${PW_A}" otterworks_a \
  "select rolsuper, rolcreatedb, rolcreaterole, rolconnlimit from pg_roles where rolname = current_user"
expect_ok     "PUBLIC holds no privilege on any otterworks database" "0" \
  admin_value otterworks "select count(*) from pg_database, aclexplode(datacl) a where datname like 'otterworks%' and a.grantee = 0"
expect_ok     "a is a member of no role" "0" \
  admin_value otterworks "select count(*) from pg_auth_members where member = '${A}'::regrole"

echo "== legacy tenant migrated to its own role"
expect_ok "legacy role owns the database" "${L}" \
  tenant_psql "${L}" "${PW_L}" otterworks_legacy "select pg_get_userbyid(datdba) from pg_database where datname = current_database()"
expect_ok "legacy role reads and writes pre-existing tables" "2" \
  tenant_psql "${L}" "${PW_L}" otterworks_legacy "insert into users (email) values ('b@example.test'); select count(*) from users"
expect_ok "legacy role can migrate pre-existing tables (ALTER)" "" \
  tenant_psql "${L}" "${PW_L}" otterworks_legacy "alter table users add column note text; alter table analytics.events add column at timestamptz"
expect_ok "every legacy object now belongs to the tenant role" "0" \
  tenant_psql "${L}" "${PW_L}" otterworks_legacy "select (select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname in ('public','analytics') and c.relowner <> (select oid from pg_roles where rolname=current_user)) + (select count(*) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proowner <> (select oid from pg_roles where rolname=current_user)) + (select count(*) from pg_type t join pg_namespace n on n.oid=t.typnamespace where n.nspname='public' and t.typname='mood' and t.typowner <> (select oid from pg_roles where rolname=current_user)) + (select count(*) from pg_namespace where nspname='analytics' and nspowner <> (select oid from pg_roles where rolname=current_user))"

echo "== isolation through PgBouncer (wildcard routing, per-login auth)"
printf '"%s" "%s"\n"%s" "%s"\n' "${A}" "${PW_A}" "${B}" "${PW_B}" > "${WORK}/userlist.txt"
cat > "${WORK}/pgbouncer.ini" <<INI
[databases]
* = host=${PG} port=5432
[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
unix_socket_dir =
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/auth/userlist.txt
pool_mode = transaction
max_user_connections = 4
INI
chmod 755 "${WORK}"; chmod 644 "${WORK}/userlist.txt" "${WORK}/pgbouncer.ini"
docker run -d --name "${PGB}" --network "${NET}" \
  -v "${WORK}/pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini:ro" -v "${WORK}:/etc/pgbouncer/auth:ro" \
  --entrypoint pgbouncer "${PGB_IMAGE}" /etc/pgbouncer/pgbouncer.ini >/dev/null
sleep 2
expect_ok     "a reaches its own database via the pooler" "${A}" \
  tenant_psql "${A}" "${PW_A}" otterworks_a "select current_user" 6432 "${PGB}"
expect_denied "a cannot reach b's database via the pooler" "permission denied for database" \
  tenant_psql "${A}" "${PW_A}" otterworks_b "select 1" 6432 "${PGB}"
expect_denied "the master login is not in the pooler's userlist" "SASL authentication failed|password authentication failed" \
  tenant_psql "${ADMIN}" "${ADMIN_PW}" otterworks_a "select 1" 6432 "${PGB}"

echo "== teardown and reaper cleanup"
tenant_db_drop_sql otterworks_b "${B}" | as_admin otterworks >/dev/null && pass "drop SQL runs"
tenant_db_drop_sql otterworks_b "${B}" | as_admin otterworks >/dev/null && pass "drop SQL is idempotent"
expect_ok "tenant b's database and role are gone" "0|0" \
  admin_value otterworks "select (select count(*) from pg_database where datname='otterworks_b') || '|' || (select count(*) from pg_roles where rolname='${B}')"
expect_denied "b's login no longer works" "password authentication failed|does not exist" \
  tenant_psql "${B}" "${PW_B}" postgres "select 1"
# Orphan: c's database dropped out-of-band, its role left behind.
as_admin otterworks <<<'DROP DATABASE otterworks_c' >/dev/null
tenant_db_orphan_roles_sql | as_admin otterworks >/dev/null
expect_ok "reaper sweep drops only roles that own no database" "0|1|1|1" \
  admin_value otterworks "select (select count(*) from pg_roles where rolname='otterworks_c_app') || '|' || (select count(*) from pg_roles where rolname='${A}') || '|' || (select count(*) from pg_roles where rolname='${L}') || '|' || (select count(*) from pg_roles where rolname='${ADMIN}')"

echo
echo "${PASSES} passed, ${FAILS} failed (${PG_IMAGE})"
[ "${FAILS}" -eq 0 ]
