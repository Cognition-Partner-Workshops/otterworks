#!/usr/bin/env bash
# shellcheck disable=SC2016 # jq filters are single-quoted on purpose
# Arm the on-call storm on one tenant, in the order the story needs:
#   0. wake the tenant if idle-suspend scaled it to zero
#   1. seed 200k synthetic documents into the tenant Postgres (seed.sh)
#   2. a real config deploy: helm upgrade --reuse-values document-service
#      with folderDigest.enabled=true and a fresh oncall_run alert label, plus a
#      Grafana annotation naming the revision (Alertmanager is reloaded first
#      so the storm opens a new oncall-devin group and pages once)
#   3. oncall-after only, with ONCALL_MIGRATE_REF=<fix branch>: alembic upgrade
#      to that branch's newest migration as soon as the rollout is ready, well
#      inside the storm alerts' for: windows, so the fixed tenant never pages
#   4. the oncall-k6 Job browsing folders through the public API host, skipped
#      with --no-load (start it later with load.sh)
# On oncall-after, a run with --no-load or ONCALL_MIGRATE_REF also silences the
# namespace's page="oncall" alerts from just before the deploy until k6 starts
# (ARM_SILENCE_MINUTES at most), so nothing in that window pages Devin or the
# incident channel a second time.
# Each step is recorded in incident/oncall/.state/<tenant>.json.
#
# Usage: [ONCALL_MIGRATE_REF=<ref>] incident/oncall/arm.sh <oncall-before|oncall-after> [--no-load]
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

tenant="${1:-}"
load=true
case "${2:-}" in
  "") ;;
  --no-load) load=false ;;
  *) die "usage: $0 <tenant> [--no-load]" ;;
esac
require_tenant "${tenant}"
require_bins git kubectl helm jq curl envsubst
ensure_kubeconfig
ns="$(tenant_ns "${tenant}")"
require_ns "${ns}"
log "Waking ${ns} (a no-op unless idle-suspend scaled it to zero)"
wake_tenant "${tenant}" "${PG_DEPLOY}" document-service api-gateway
require_chart_keys

active="$(kubectl -n "${ns}" get job "${K6_JOB}" -o jsonpath='{.status.active}' 2>/dev/null || true)"
[ -z "${active}" ] || [ "${active}" = 0 ] ||
  die "${tenant} is already armed (Job ${K6_JOB} is running); run make oncall-disarm TENANT=${tenant} first"

# CD finishes a push from a Job in the platform namespace after its workflow
# run ends, and that Job's helm upgrade would replace this arm's revision.
for job in $(kubectl -n "${PLATFORM_NS}" get jobs -o json |
  jq -r --arg p "deploy-${tenant}-" '.items[] | select((.metadata.name | startswith($p)) and (.status.active // 0) > 0) | .metadata.name'); do
  log "Waiting for the CD deploy Job ${PLATFORM_NS}/${job} to finish"
  kubectl -n "${PLATFORM_NS}" wait --for=condition=complete "job/${job}" --timeout=20m >/dev/null ||
    die "CD deploy Job ${PLATFORM_NS}/${job} did not complete; arm once it has"
done

# The storm only reproduces on the dedicated Postgres: fail closed if
# document-service still points at the shared RDS database.
db_secret="$(kubectl -n "${ns}" get deploy document-service -o json |
  jq -r '[.spec.template.spec.containers[].env[]? | select(.name == "DOC_SVC_DATABASE_URL")
          | .valueFrom.secretKeyRef.name // empty] | first // empty')"
[ "${db_secret}" = oncall-postgres ] ||
  die "document-service in ${ns} does not read DOC_SVC_DATABASE_URL from Secret oncall-postgres; run make oncall-up"

# Resolve the fix and its revision before anything changes, so a bad ref fails
# while the worker is still off.
migrate_ref="${ONCALL_MIGRATE_REF:-}"
migrate_commit=""
migrate_rev=""
if [ -n "${migrate_ref}" ]; then
  [ "${tenant}" = "${AFTER_TENANT}" ] ||
    die "ONCALL_MIGRATE_REF applies the fix, and only ${AFTER_TENANT} takes it; ${tenant} must stay unfixed"
  migrate_commit="$(resolve_ref "${migrate_ref}")" || migrate_commit=""
  [ -n "${migrate_commit}" ] || die "ONCALL_MIGRATE_REF=${migrate_ref} is neither a branch on origin nor a local ref"
  migrate_rev="$(branch_alembic_head "${migrate_commit}")"
  branch="$(tenant_branch "${tenant}")"
  git -C "${REPO}" fetch -q origin "+refs/heads/${branch}:refs/remotes/origin/${branch}" ||
    die "could not fetch ${branch}"
  shipped="$(branch_alembic_head "origin/${branch}")"
  if [ -z "${migrate_rev}" ] || ! [[ "${migrate_rev}" > "${shipped}" ]]; then
    die "${migrate_ref} ships no migration newer than ${branch} (${shipped:-none}); nothing to apply"
  fi
  log "The fix: alembic ${migrate_rev} from ${migrate_ref} (${migrate_commit:0:12}), applied right after the rollout"
fi
silence=false
if [ "${tenant}" = "${AFTER_TENANT}" ] && { [ "${load}" = false ] || [ -n "${migrate_ref}" ]; }; then
  silence=true
fi

state_init "${tenant}"
state_update "${tenant}" '.run_id = $run | .armed_at = $at | .steps = {} | del(.disarmed_at)' \
  --arg run "${RUN_ID}" --arg at "$(now_iso)"

# ---------- 1. seed ----------
log "Step 1/4: seed"
"${ONCALL_DIR}/seed.sh" "${tenant}"
owner="$(state_get "${tenant}" .owner_id)"
[ -n "${owner}" ] || die "seed.sh did not record the demo owner id"

# ---------- 2. config deploy ----------
log "Step 2/4: config deploy (folderDigest.enabled=true)"
previous="$(helm_revision "${tenant}")"
oncall_run="$(date +%s)"
reloaded_at=""
lingered=false
pf_prometheus
pf_alertmanager
if oncall_group_may_linger "${ns}"; then
  lingered=true
  am_reload
  reloaded_at="$(now_iso)"
  log "Alertmanager reloaded to drop the previous storm's oncall-devin group for ${ns}"
fi
log "Storm alerts from this arm carry oncall_run=${oncall_run}"
silence_id=""
if [ "${silence}" = true ]; then
  silence_id="$(am_silence_arm "${ns}" "${ARM_SILENCE_MINUTES}")"
  [ -n "${silence_id}" ] || die "Alertmanager did not create the silence for ${ns}"
  log "page=\"oncall\" alerts in ${ns} silenced for up to ${ARM_SILENCE_MINUTES} min (until k6 starts): ${silence_id}"
  state_update "${tenant}" '.steps.silence = {at: $at, id: $id, minutes: $min}' \
    --arg at "$(now_iso)" --arg id "${silence_id}" --argjson min "${ARM_SILENCE_MINUTES}"
fi
digest_deploy "${tenant}" true "${oncall_run}"
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
                    set: {"folderDigest.enabled": true, "folderDigest.intervalSeconds": $iv, "folderDigest.concurrency": $cc,
                          "monitoring.rules.extraLabels.oncall_run": $run},
                    oncall_run: $run, previous_group_may_linger: $linger, alertmanager_reloaded_at: $reload,
                    annotation_id: $ann}' \
  --arg at "${deployed_at}" --argjson prev "${previous:-0}" --argjson rev "${revision}" \
  --arg run "${oncall_run}" --arg reload "${reloaded_at}" --argjson linger "${lingered}" \
  --argjson iv "${DIGEST_INTERVAL_SECONDS}" --argjson cc "${DIGEST_CONCURRENCY}" \
  --arg ann "${ANNOTATION_ID}"

# ---------- 3. the fix ----------
if [ -n "${migrate_ref}" ]; then
  log "Step 3/4: alembic upgrade ${migrate_rev} from ${migrate_ref}"
  migrate_from_ref "${tenant}" "${migrate_commit}" "${migrate_rev}"
  migrated_at="$(now_iso)"
  index="$(pg "${tenant}" -At -c "SELECT to_regclass('public.${FIX_INDEX}') IS NOT NULL")"
  [ "${index}" = t ] || warn "${ns} has no ${FIX_INDEX} after migration ${migrate_rev}"
  log "${ns} Postgres at alembic ${migrate_rev} $(( $(date -u -d "${migrated_at}" +%s) - $(date -u -d "${deployed_at}" +%s) ))s after the rollout"
  state_update "${tenant}" '.steps.migrate = {at: $at, ref: $ref, commit: $commit, revision: $rev, index: $idx}' \
    --arg at "${migrated_at}" --arg ref "${migrate_ref}" --arg commit "${migrate_commit}" \
    --arg rev "${migrate_rev}" --argjson idx "$([ "${index}" = t ] && echo true || echo false)"
else
  log "Step 3/4: no fix to apply (ONCALL_MIGRATE_REF unset)"
fi

# ---------- 4. load ----------
if [ "${load}" = true ]; then
  if [ "${silence}" = true ]; then
    n="$(am_silence_expire "${ns}")"
    log "Expired ${n} harness silence(s) on ${ns}; pages count again from here"
  fi
  log "Step 4/4: k6 load (${LOAD_VUS} VUs, ${LOAD_MINUTES} min) against https://$(api_host "${tenant}")"
  start_load "${tenant}"
else
  log "Step 4/4: skipped (--no-load); start it with make oncall-load TENANT=${tenant}"
  exit 0
fi

if [ -n "${migrate_ref}" ]; then
  log "Armed ${tenant} with the fix. No storm alert should fire; gate after 5 minutes of load:"
  log "make oncall-verify TENANT=${tenant} EXPECT=after"
  exit 0
fi
log "Armed ${tenant}. The first storm alerts fire within about 6 minutes of the deploy;"
log "the single page to Devin follows Alertmanager's 3 minute group_wait."
log "Watch: make oncall-status TENANT=${tenant}   Gate: make oncall-verify TENANT=${tenant} EXPECT=before"
