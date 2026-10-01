#!/usr/bin/env bash
# shellcheck disable=SC2016 # jq filters are single-quoted on purpose
# Seed one on-call tenant: register the demo user through auth-service, then
# load the synthetic documents into the tenant Postgres with seed.sql.
# Idempotent. Prints counts, never the demo user's password or token.
#
# Usage: incident/oncall/seed.sh <oncall-before|oncall-after>
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

tenant="${1:-}"
require_tenant "${tenant}"
require_bins kubectl jq curl openssl
ensure_kubeconfig
ns="$(tenant_ns "${tenant}")"
require_ns "${ns}"

# ---------- demo user ----------
# The password is generated once and kept in Secret oncall-demo-user so the
# presenter can log in at https://t-<tenant>.demo.otterworks.app.
ensure_demo_password() {
  if [ -z "$(secret_value "${ns}" oncall-demo-user password)" ]; then
    log "Creating Secret ${ns}/oncall-demo-user (demo login password)"
    DEMO_PASSWORD="$(openssl rand -hex 12)" jq -n \
      --arg ns "${ns}" --arg email "${DEMO_USER_EMAIL}" \
      '{apiVersion: "v1", kind: "Secret", type: "Opaque",
        metadata: {name: "oncall-demo-user", namespace: $ns,
                   labels: {"app.kubernetes.io/part-of": "oncall-storm"}},
        stringData: {email: $email, password: env.DEMO_PASSWORD}}' |
      kubectl apply -f - >/dev/null
  fi
}

# Prints the demo user's id. Register first; an existing account logs in.
demo_user_id() {
  local base="http://localhost:${GATEWAY_PORT}/api/v1/auth" body code out id
  out="$(mktemp)"
  chmod 600 "${out}"
  body="$(DEMO_PASSWORD="$(secret_value "${ns}" oncall-demo-user password)" jq -nc \
    --arg email "${DEMO_USER_EMAIL}" \
    '{email: $email, password: env.DEMO_PASSWORD, displayName: "On-call Demo"}')"
  code="$(printf '%s' "${body}" | curl -sS --max-time 20 -o "${out}" -w '%{http_code}' \
    -H 'Content-Type: application/json' --data @- "${base}/register")" || code=000
  if [ "${code}" != 200 ] && [ "${code}" != 201 ]; then
    code="$(printf '%s' "${body}" | jq -c '{email, password}' |
      curl -sS --max-time 20 -o "${out}" -w '%{http_code}' \
        -H 'Content-Type: application/json' --data @- "${base}/login")" || code=000
  fi
  id="$(jq -r '.user.id // empty' "${out}" 2>/dev/null || true)"
  rm -f "${out}"
  [ "${code}" = 200 ] || [ "${code}" = 201 ] ||
    die "auth-service refused register and login for ${DEMO_USER_EMAIL} (HTTP ${code}); if the account predates Secret oncall-demo-user, delete the user or the Secret and retry"
  [ -n "${id}" ] || die "auth-service answered without a user id"
  echo "${id}"
}

ensure_demo_password
pf_start "${ns}" svc/api-gateway "${GATEWAY_PORT}" 8080 /health
owner="$(demo_user_id)"
log "Demo user ${DEMO_USER_EMAIL} has id ${owner}"

# ---------- documents ----------
kubectl -n "${ns}" rollout status "deploy/${PG_DEPLOY}" --timeout=3m >/dev/null ||
  die "${PG_DEPLOY} is not ready in ${ns}"
for _ in $(seq 1 60); do
  [ "$(pg "${tenant}" -At -c "SELECT to_regclass('public.documents') IS NOT NULL")" = t ] && break
  sleep 5
done
[ "$(pg "${tenant}" -At -c "SELECT to_regclass('public.documents') IS NOT NULL")" = t ] ||
  die "table documents does not exist in ${ns}; document-service has not migrated the tenant Postgres"

log "Seeding ${SEED_DOCUMENTS} documents in ${SEED_FOLDERS} folders (${SEED_VERSIONS_PER_DOC} versions each) into ${ns}"
started="$(date +%s)"
counts="$(pg "${tenant}" -At \
  -v owner="${owner}" -v documents="${SEED_DOCUMENTS}" \
  -v folders="${SEED_FOLDERS}" -v versions="${SEED_VERSIONS_PER_DOC}" \
  -f - <"${ONCALL_DIR}/seed.sql" | tail -n 1)"
elapsed=$(( $(date +%s) - started ))
log "${counts} (${elapsed}s)"

docs="$(sed -E 's/.*owner_documents=([0-9]+).*/\1/' <<<"${counts}")"
[ "${docs}" -ge "${SEED_DOCUMENTS}" ] ||
  die "only ${docs} documents belong to ${owner}; expected ${SEED_DOCUMENTS}"
if [ "$(pg "${tenant}" -At -c "SELECT count(*) FROM pg_indexes WHERE tablename = 'documents' AND indexdef ILIKE '%(folder_id%'")" != 0 ]; then
  log "documents has an index on folder_id in ${ns} (the migration 005 fix); make oncall-reset drops it"
fi

state_update "${tenant}" \
  '.owner_id = $owner | .steps.seed = {at: $at, documents: $d, folders: $f, versions_per_document: $v, seconds: $s, counts: $c}' \
  --arg owner "${owner}" --arg at "$(now_iso)" --arg c "${counts}" \
  --argjson d "${SEED_DOCUMENTS}" --argjson f "${SEED_FOLDERS}" \
  --argjson v "${SEED_VERSIONS_PER_DOC}" --argjson s "${elapsed}"
