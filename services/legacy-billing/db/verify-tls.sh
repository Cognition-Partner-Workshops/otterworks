#!/usr/bin/env bash
set -euo pipefail

db_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$db_dir/../../.." && pwd)"

announce() {
  printf '\n==> %s\n' "$1"
}

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

if ! command -v docker >/dev/null 2>&1; then
  fail "docker is required"
fi
if [[ -z "${NS:-}" ]]; then
  fail "NS is required"
fi
if ! docker image inspect postgres:16 >/dev/null 2>&1; then
  fail "local postgres:16 image is required; the verifier does not pull images"
fi

cd "$repo_root"
compose=(
  docker compose
  -f docker-compose.procs.yml
  -f docker-compose.procs.tls.yml
  -p "otterworks-procs-$NS"
)

cleanup() {
  status=$?
  trap - EXIT
  "${compose[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  printf 'Cleaned TLS Compose project otterworks-procs-%s with down -v.\n' "$NS"
  exit "$status"
}
trap cleanup EXIT

announce "Start the isolated TLS stack"
"${compose[@]}" up -d --build --wait

announce "Print PostgreSQL server version through the application connection"
"${compose[@]}" exec -T legacy-billing python - <<'PY'
import app

with app.db_connect() as connection:
    print(connection.execute("SELECT version()").fetchone()[0])
PY

announce "Check the application health endpoint and three seeded plans"
health="$(curl -fsS "http://127.0.0.1:${PROCS_APP_PORT}/health")"
printf '%s\n' "$health"
python3 -c 'import json,sys; assert json.loads(sys.argv[1])["status"] == "UP"' "$health"
plans="$(curl -fsS "http://127.0.0.1:${PROCS_APP_PORT}/plans")"
printf '%s\n' "$plans"
python3 -c 'import json,sys; assert len(json.loads(sys.argv[1])) == 3' "$plans"

announce "Assert non-superuser application identity and verified TLS"
"${compose[@]}" exec -T legacy-billing python - <<'PY'
import json
import os

import app

with app.db_connect() as connection:
    user, is_superuser, ssl, version, cipher = connection.execute(
        """
        SELECT current_user, role.rolsuper, stats.ssl, stats.version, stats.cipher
        FROM pg_roles AS role, pg_stat_ssl AS stats
        WHERE role.rolname = current_user
          AND stats.pid = pg_backend_pid()
        """
    ).fetchone()
    evidence = {
        "current_user": user,
        "rolsuper": is_superuser,
        "pg_stat_ssl": {"ssl": ssl, "version": version, "cipher": cipher},
        "sslmode": os.getenv("DB_SSLMODE"),
        "sslrootcert": os.getenv("DB_SSLROOTCERT"),
        "parameters": connection.info.get_parameters(),
        "ssl_in_use": connection.pgconn.ssl_in_use,
    }
    print(json.dumps(evidence, default=str, sort_keys=True))
    assert user == "billing_app"
    assert is_superuser is False
    assert ssl is True and version and cipher
    assert evidence["sslmode"] == "verify-full"
    assert evidence["sslrootcert"] == "/tls/ca.crt"
    assert connection.pgconn.ssl_in_use
PY

announce "Assert billing_app cannot connect without TLS"
"${compose[@]}" exec -T -e DB_SSLMODE=disable legacy-billing python - <<'PY'
import app

try:
    app.db_connect()
except Exception as exc:
    message = str(exc).lower()
    print(f"Expected TLS-disabled rejection: {exc}")
    if "pg_hba.conf" not in message or "no encryption" not in message:
        raise SystemExit("connection failed for an unexpected reason")
else:
    raise SystemExit("billing_app unexpectedly connected with TLS disabled")
PY

announce "Assert verify-full rejects a hostname outside the certificate SAN"
db_ip="$("${compose[@]}" exec -T legacy-billing-db hostname -i | awk '{print $1}')"
[[ -n "$db_ip" ]] || fail "could not determine the database container IP"
"${compose[@]}" exec -T -e "DB_HOST=$db_ip" legacy-billing python - <<'PY'
import app

try:
    app.db_connect()
except Exception as exc:
    message = str(exc).lower()
    print(f"Expected hostname verification rejection: {exc}")
    if not any(
        expected in message
        for expected in ("does not match host name", "does not match", "ip address mismatch")
    ):
        raise SystemExit("connection failed for an unexpected reason")
else:
    raise SystemExit("verify-full unexpectedly accepted the database IP")
PY

announce "Assert the baked RDS bundle rejects the local throwaway CA"
"${compose[@]}" exec -T legacy-billing test -s /etc/ssl/certs/rds-global-bundle.pem
"${compose[@]}" exec -T \
  -e DB_SSLROOTCERT=/etc/ssl/certs/rds-global-bundle.pem \
  legacy-billing python - <<'PY'
import app

try:
    app.db_connect()
except Exception as exc:
    message = str(exc).lower()
    print(f"Expected certificate verification rejection: {exc}")
    if "certificate verify failed" not in message:
        raise SystemExit("connection failed for an unexpected reason")
else:
    raise SystemExit("the RDS bundle unexpectedly trusted the local CA")
PY

announce "Assert billing_app cannot delete billing tenants"
"${compose[@]}" exec -T legacy-billing python - <<'PY'
import app
import psycopg

try:
    with app.db_connect() as connection:
        connection.execute("DELETE FROM billing.tenants")
except psycopg.errors.InsufficientPrivilege as exc:
    print(f"Expected permission denial: {exc}")
else:
    raise SystemExit("billing_app unexpectedly deleted from billing.tenants")
PY

printf '\ng-billing-tls: PASS\n'
