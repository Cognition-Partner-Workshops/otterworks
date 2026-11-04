#!/usr/bin/env bash
# Unit tests for the per-tenant DB login plumbing in scripts/lib/tenant-common.sh
# and demo-platform/scripts/install-pgbouncer.sh: role naming, the PgBouncer
# userlist upsert/remove, the admin Job manifest, and that install-pgbouncer.sh
# keeps tenant logins when it rewrites the master one. kubectl is stubbed with
# an in-memory Secret store; this runs anywhere (needs jq, python3 + PyYAML
# for the manifest check). The SQL itself is exercised against a real Postgres
# by scripts/tests/test-tenant-db-isolation.sh.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=/dev/null
source "${REPO_ROOT}/scripts/lib/tenant-common.sh"

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); printf '  ok   %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (want '$3', got '$2')"; fi; }

STORE="$(mktemp -d)"; trap 'rm -rf "${STORE}"' EXIT
echo 0 > "${STORE}/conflicts"
# Minimal kubectl: get/replace/apply of secret pgbouncer-auth (JSON on disk),
# rollout restart recorded; everything else captured for inspection.
kubectl() {
  local args="$*"
  case "${args}" in
    *"get secret pgbouncer-auth -o json"*)
      [ -f "${STORE}/secret.json" ] || return 1; cat "${STORE}/secret.json" ;;
    "replace -f -")
      # Counter on disk: replace runs at the end of a pipeline, in a subshell.
      local n; n="$(cat "${STORE}/conflicts")"
      if [ "${n}" -gt 0 ]; then echo $((n - 1)) > "${STORE}/conflicts"; cat >/dev/null; return 1; fi
      jq '.metadata.resourceVersion = ((.metadata.resourceVersion // "0" | tonumber) + 1 | tostring)' \
        > "${STORE}/secret.json" ;;
    *apply*"-f -"*) cat >> "${STORE}/applied.yaml"; printf -- '---\n' >> "${STORE}/applied.yaml" ;;
    *"rollout restart"*) echo restart >> "${STORE}/restarts" ;;
    *) cat >/dev/null 2>&1 || true; return 0 ;;
  esac
}
sleep() { :; }
seed_userlist() {
  USERLIST="$1" jq -n '{apiVersion:"v1",kind:"Secret",metadata:{name:"pgbouncer-auth",resourceVersion:"1"},
                        data:{"userlist.txt":($ENV.USERLIST|@base64)}}' > "${STORE}/secret.json"
}
userlist() { jq -r '.data["userlist.txt"] | @base64d' "${STORE}/secret.json"; }

echo "== tenant_db_role"
check "role name is <db>_app" "$(tenant_db_role otterworks_a01)" "otterworks_a01_app"
long="otterworks_$(printf 'x%.0s' $(seq 1 52))"
r1="$(tenant_db_role "${long}")"; r2="$(tenant_db_role "${long}y")"
check "overlong role name fits Postgres' 63-byte limit" "${#r1}" "63"
if [ "${r1}" != "${r2}" ]; then ok "overlong names stay distinct"; else bad "overlong names collide"; fi
check "overlong role still ends in _app" "${r1: -4}" "_app"
pw="$(gen_db_password)"
if printf '%s' "${pw}" | grep -Eq '^[0-9a-f]{48}$'; then ok "generated password is 48 hex chars"; else bad "password format"; fi

echo "== pgbouncer_userlist_set"
pgbouncer_userlist_set otterworks_a_app pw >/dev/null; check "no pooler Secret -> rc 2" "$?" "2"
seed_userlist $'"otterworks_admin" "adminpw"\n'
pgbouncer_userlist_set otterworks_a_app pwA >/dev/null; check "add tenant line -> rc 0" "$?" "0"
check "admin line kept, tenant line added" "$(userlist)" $'"otterworks_admin" "adminpw"\n"otterworks_a_app" "pwA"'
pgbouncer_userlist_set otterworks_a_app pwA >/dev/null; check "unchanged -> rc 1 (no restart needed)" "$?" "1"
echo 2 > "${STORE}/conflicts"
pgbouncer_userlist_set otterworks_b_app pwB >/dev/null; check "retries through resourceVersion conflicts" "$?" "0"
pgbouncer_userlist_set otterworks_a_app pwA2 >/dev/null
check "password change replaces the line in place" "$(userlist | grep -c otterworks_a_app)|$(userlist | grep otterworks_a_app)" '1|"otterworks_a_app" "pwA2"'
pgbouncer_userlist_set otterworks_a >/dev/null
check "prefix of another role name is not matched" "$(userlist | grep -c otterworks_a_app)" "1"
pgbouncer_userlist_set otterworks_a_app >/dev/null; check "remove tenant line -> rc 0" "$?" "0"
check "only the other lines remain" "$(userlist)" $'"otterworks_admin" "adminpw"\n"otterworks_b_app" "pwB"'

echo "== run_db_admin_job manifest"
# shellcheck disable=SC2034  # read by run_db_admin_job
RDS_HOST=db.example.internal RDS_PORT=5432 DB_USER=otterworks_admin DB_PASSWORD=adminpw
: > "${STORE}/applied.yaml"
run_db_admin_job otterworks-a tenant-db-init 1s "SELECT 1;" "TENANT_DB_PASSWORD=tenant-db-app:password" >/dev/null 2>&1
if python3 - "${STORE}/applied.yaml" <<'PY'
import sys, yaml
docs = [d for d in yaml.safe_load_all(open(sys.argv[1])) if d]
kinds = {d["kind"]: d for d in docs}
assert set(kinds) == {"Secret", "ConfigMap", "Job"}, kinds.keys()
assert kinds["ConfigMap"]["data"]["script.sql"] == "SELECT 1;"
c = kinds["Job"]["spec"]["template"]["spec"]["containers"][0]
env = {e["name"]: e["valueFrom"]["secretKeyRef"] for e in c["env"]}
assert env["PGPASSWORD"] == {"name": "tenant-db-init-admin", "key": "PGPASSWORD"}, env
assert env["TENANT_DB_PASSWORD"] == {"name": "tenant-db-app", "key": "password"}, env
assert "adminpw" not in yaml.safe_dump(kinds["Job"]), "master password inlined into the Job"
assert "adminpw" not in kinds["ConfigMap"]["data"]["script.sql"]
PY
then ok "Secret + ConfigMap + Job; passwords only via secretKeyRef"; else bad "admin Job manifest"; fi
if tenant_db_provision_sql otterworks_a otterworks_a_app | grep -q "pwA\|adminpw"; then bad "provisioning SQL holds a password"
else ok "provisioning SQL holds no password"; fi

echo "== install-pgbouncer.sh keeps tenant logins"
seed_userlist $'"otterworks_admin" "old"\n"otterworks_a_app" "pwA"\n'
: > "${STORE}/applied.yaml"
# shellcheck disable=SC2034  # read by the eval'd installer block
NS=otterworks-platform
# Run just the userlist block of the installer against the stub.
eval "$(sed -n '/^tenant_lines=/,/kubectl apply -f - >\/dev\/null$/p' "${REPO_ROOT}/demo-platform/scripts/install-pgbouncer.sh")"
got="$(python3 -c 'import sys,yaml; d=[x for x in yaml.safe_load_all(open(sys.argv[1])) if x][0]; print(d["stringData"]["userlist.txt"], end="")' "${STORE}/applied.yaml")"
check "master line rewritten, tenant line carried over" "${got}" $'"otterworks_admin" "adminpw"\n"otterworks_a_app" "pwA"'

echo
echo "${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
