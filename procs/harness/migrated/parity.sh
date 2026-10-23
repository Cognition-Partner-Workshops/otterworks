#!/usr/bin/env bash
# g-procs-parity on the migrated schema. Expects `make procs-up-migrated NS=<ns>`:
# postgres:16 built by bootstrap/roles.sql + db/migrate.sh (never schema.sql),
# legacy-billing connected as billing_app with DB_SSLMODE=verify-full. Every
# recorded scenario of every module is replayed as billing_app over verify-full
# TLS, after a fresh migrate.sh rebuild, against the immutable transcripts.
set -euo pipefail

: "${NS:?NS is required}"
: "${PROCS_MIGRATED_DB_PORT:?PROCS_MIGRATED_DB_PORT is required (run via make)}"
: "${PROCS_MIGRATED_APP_PORT:?PROCS_MIGRATED_APP_PORT is required (run via make)}"

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
compose_file="$root/docker-compose.procs.migrated.yml"
project="otterworks-procs-migrated-$NS"
compose=(docker compose -f "$compose_file" -p "$project")
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

"${compose[@]}" cp legacy-billing-db:/tls/ca.crt "$work/ca.crt" 2>/dev/null
"${compose[@]}" logs --no-log-prefix legacy-billing-migrate | tail -n 1

echo "== legacy-billing (container) -> migrated database, through app.db_connect()"
"${compose[@]}" exec -T legacy-billing python - <<'PY'
import os

from app import db_connect

with db_connect() as connection, connection.cursor() as cursor:
    cursor.execute(
        """
        SELECT current_user, r.rolsuper, s.ssl, s.version, current_setting('server_version'),
               has_schema_privilege('billing_migrations', 'USAGE')
        FROM pg_roles AS r, pg_stat_ssl AS s
        WHERE r.rolname = current_user AND s.pid = pg_backend_pid()
        """
    )
    user, superuser, ssl, tls, server, sees_ledger = cursor.fetchone()
print(f"user={user} rolsuper={superuser} ssl={ssl} {tls} sslmode={os.environ['DB_SSLMODE']} "
      f"rootcert={os.environ['DB_SSLROOTCERT']} server={server} migration_ledger_visible={sees_ledger}")
assert user == "billing_app" and not superuser and ssl and os.environ["DB_SSLMODE"] == "verify-full"
assert server.startswith("16."), server
assert not sees_ledger, "billing_app must not see the migration ledger"
PY
python3 - "$PROCS_MIGRATED_APP_PORT" <<'PY'
import json
import sys
import urllib.request

base = f"http://127.0.0.1:{sys.argv[1]}"
health = json.load(urllib.request.urlopen(f"{base}/health", timeout=10))
plans = json.load(urllib.request.urlopen(f"{base}/plans", timeout=10))
print(f"GET /health -> {health}; GET /plans -> {[plan['code'] for plan in plans]}")
assert health.get("status") in {"ok", "healthy", "UP"}, health
assert plans, "no plans returned"
PY

echo "== replay all modules as billing_app over verify-full TLS, rebuilding with migrate.sh per scenario"
export DB_HOST=localhost
export DB_PORT="$PROCS_MIGRATED_DB_PORT"
export DB_NAME="billing_$NS"
export DB_USER=billing_app
export DB_PASSWORD="${BILLING_APP_PASSWORD:-billing_app}"
export DB_SSLMODE=verify-full
export DB_SSLROOTCERT="$work/ca.crt"
printf -v PROCS_SCHEMA_RESET_COMMAND '%q ' "${compose[@]}" run --rm --no-deps -e BILLING_REBUILD_RESET=1 legacy-billing-migrate
export PROCS_SCHEMA_RESET_COMMAND
cd "$root"
uv run --with 'psycopg[binary]==3.2.9' --with pyyaml==6.0.2 procs/harness/schema_parity.py \
  --label migrated --expect-user billing_app --require-tls "$@"
