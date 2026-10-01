#!/usr/bin/env bash
# shellcheck disable=SC2016 # jq filters are single-quoted on purpose
# Arm the on-call storm on one tenant, in the order the story needs:
#   1. seed 200k synthetic documents into the tenant Postgres (seed.sh)
#   2. a real config deploy: helm upgrade --reuse-values document-service
#      with folderDigest.enabled=true, plus a Grafana annotation naming the
#      revision
#   3. the oncall-k6 Job browsing folders through the public API host
# Each step is recorded in incident/oncall/.state/<tenant>.json.
#
# Usage: incident/oncall/arm.sh <oncall-before|oncall-after>
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

tenant="${1:-}"
require_tenant "${tenant}"
require_bins kubectl helm jq curl envsubst
ensure_kubeconfig
ns="$(tenant_ns "${tenant}")"
require_ns "${ns}"
require_chart_keys

active="$(kubectl -n "${ns}" get job "${K6_JOB}" -o jsonpath='{.status.active}' 2>/dev/null || true)"
[ -z "${active}" ] || [ "${active}" = 0 ] ||
  die "${tenant} is already armed (Job ${K6_JOB} is running); run make oncall-disarm TENANT=${tenant} first"

# The storm only reproduces on the dedicated Postgres: fail closed if
# document-service still points at the shared RDS database.
db_secret="$(kubectl -n "${ns}" get deploy document-service -o json |
  jq -r '[.spec.template.spec.containers[].env[]? | select(.name == "DOC_SVC_DATABASE_URL")
          | .valueFrom.secretKeyRef.name // empty] | first // empty')"
[ "${db_secret}" = oncall-postgres ] ||
  die "document-service in ${ns} does not read DOC_SVC_DATABASE_URL from Secret oncall-postgres; run make oncall-up"

state_init "${tenant}"
state_update "${tenant}" '.run_id = $run | .armed_at = $at | .steps = {} | del(.disarmed_at)' \
  --arg run "${RUN_ID}" --arg at "$(now_iso)"

# ---------- 1. seed ----------
log "Step 1/3: seed"
"${ONCALL_DIR}/seed.sh" "${tenant}"
owner="$(state_get "${tenant}" .owner_id)"
[ -n "${owner}" ] || die "seed.sh did not record the demo owner id"

# ---------- 2. config deploy ----------
log "Step 2/3: config deploy (folderDigest.enabled=true)"
previous="$(helm_revision "${tenant}")"
digest_deploy "${tenant}" true
revision="$(helm_revision "${tenant}")"
if [ -z "${revision}" ] || [ "${revision}" = "${previous}" ]; then
  die "helm did not record a new document-service revision in ${ns}"
fi
flag="$(kubectl -n "${ns}" get deploy document-service -o json |
  jq -r '[.spec.template.spec.containers[].env[]? | select(.name == "DOC_SVC_FOLDER_DIGEST_ENABLED") | .value] | first // empty')"
[ "${flag}" = true ] ||
  die "revision ${revision} rendered no DOC_SVC_FOLDER_DIGEST_ENABLED=true; the chart does not wire folderDigest.enabled"
deployed_at="$(now_iso)"
grafana_annotate "${tenant}" "document-service rev ${revision}: folder digest worker enabled"
log "document-service rev ${revision} (was ${previous}) is live; annotation ${ANNOTATION_ID:-none}"
state_update "${tenant}" \
  '.steps.deploy = {at: $at, release: "document-service", previous_revision: $prev, revision: $rev,
                    set: {"folderDigest.enabled": true, "folderDigest.intervalSeconds": $iv, "folderDigest.concurrency": $cc},
                    annotation_id: $ann}' \
  --arg at "${deployed_at}" --argjson prev "${previous:-0}" --argjson rev "${revision}" \
  --argjson iv "${DIGEST_INTERVAL_SECONDS}" --argjson cc "${DIGEST_CONCURRENCY}" \
  --arg ann "${ANNOTATION_ID}"

# ---------- 3. load ----------
log "Step 3/3: k6 load (${LOAD_VUS} VUs, ${LOAD_MINUTES} min) against https://$(api_host "${tenant}")"
kubectl -n "${ns}" create configmap "${K6_CONFIGMAP}" \
  --from-file=folders.js="${ONCALL_DIR}/k6/folders.js" --dry-run=client -o yaml |
  kubectl -n "${ns}" apply -f - >/dev/null
kubectl -n "${ns}" delete job "${K6_JOB}" --ignore-not-found --wait=true >/dev/null
K6_DEADLINE_SECONDS="$(awk -v m="${LOAD_MINUTES}" 'BEGIN { printf "%d", m * 60 + 600 }')"
TENANT="${tenant}" API_HOST="$(api_host "${tenant}")" OWNER_ID="${owner}" \
  K6_DEADLINE_SECONDS="${K6_DEADLINE_SECONDS}" \
  render "${ONCALL_DIR}/k8s/k6-job.yaml" RUN_ID K6_DEADLINE_SECONDS API_HOST TENANT OWNER_ID \
    DEMO_USER_EMAIL SEED_FOLDERS LOAD_VUS LOAD_MINUTES P95_SLO_SECONDS |
  kubectl -n "${ns}" apply -f - >/dev/null
kubectl -n "${ns}" wait --for=condition=Ready pod -l app=oncall-k6 --timeout=3m >/dev/null ||
  die "the ${K6_JOB} pod did not start in ${ns}; kubectl -n ${ns} describe job ${K6_JOB}"
state_update "${tenant}" \
  '.steps.load = {at: $at, job: $job, vus: $vus, minutes: $min, url: $url}' \
  --arg at "$(now_iso)" --arg job "${K6_JOB}" --arg url "https://$(api_host "${tenant}")" \
  --argjson vus "${LOAD_VUS}" --argjson min "${LOAD_MINUTES}"

log "Armed ${tenant}. The first storm alerts fire within about 6 minutes of the deploy;"
log "the single page to Devin follows Alertmanager's 3 minute group_wait."
log "Watch: make oncall-status TENANT=${tenant}   Gate: make oncall-verify TENANT=${tenant} EXPECT=before"
