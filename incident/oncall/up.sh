#!/usr/bin/env bash
# Stand up the on-call storm estate:
#   1. both tenants: push origin/main to demo-oncall-before / demo-oncall-after
#      only when a branch does not exist (CD then creates the tenant); an
#      existing branch whose tenant is gone is redeployed with tenant.sh sync
#   2. wait for CD, wake the tenants (scripts/tenant-scale.sh <id> up)
#   3. Secret oncall-postgres (generated once) and the tenant Postgres
#   4. document-service ready on that dedicated database
#   5. the incident channel and the platform pieces
# Safe to re-run.
#
# Usage: incident/oncall/up.sh
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_bins git kubectl helm jq curl openssl envsubst
ensure_kubeconfig
CD_TIMEOUT="${ONCALL_CD_TIMEOUT:-1800}"

git -C "${REPO}" fetch -q origin main
main_sha="$(git -C "${REPO}" rev-parse origin/main)"

# ---------- 1. branches ----------
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  branch="$(tenant_branch "${tenant}")"
  if git -C "${REPO}" ls-remote --exit-code --heads origin "${branch}" >/dev/null 2>&1; then
    if kubectl get ns "$(tenant_ns "${tenant}")" >/dev/null 2>&1; then
      log "${branch} exists and ${tenant} is deployed"
    else
      log "${branch} exists but ${tenant} is gone; redeploying through the ops dashboard"
      CD_TTL="${TENANT_TTL}" "${REPO}/demo-platform/scripts/tenant.sh" sync "${branch}"
    fi
  else
    log "Creating ${branch} at origin/main (${main_sha:0:12}); CD creates ${tenant}"
    git -C "${REPO}" push -q origin "${main_sha}:refs/heads/${branch}"
  fi
done

# ---------- 2. wait for CD, wake ----------
# document-service reads DOC_SVC_DATABASE_URL from Secret oncall-postgres
# (overlay database.urlSecret), so the Secret is created as soon as the
# namespace exists; CD's pod then starts instead of waiting on a missing key.
ensure_pg_secret() {
  local ns="$1"
  if [ -n "$(secret_value "${ns}" oncall-postgres url)" ]; then
    log "Secret ${ns}/oncall-postgres exists; keeping it"
    return 0
  fi
  log "Creating Secret ${ns}/oncall-postgres"
  PG_PASSWORD="$(openssl rand -hex 24)" jq -n --arg ns "${ns}" \
    '{apiVersion: "v1", kind: "Secret", type: "Opaque",
      metadata: {name: "oncall-postgres", namespace: $ns,
                 labels: {"app.kubernetes.io/part-of": "oncall-storm"}},
      stringData: {password: env.PG_PASSWORD,
                   url: ("postgresql+asyncpg://otterworks:" + env.PG_PASSWORD + "@oncall-postgres:5432/otterworks")}}' |
    kubectl apply -f - >/dev/null
}

wait_for_tenant() {
  local tenant="$1" ns deadline
  ns="$(tenant_ns "${tenant}")"
  deadline=$(( $(date +%s) + CD_TIMEOUT ))
  log "Waiting up to ${CD_TIMEOUT}s for CD to deploy ${tenant}"
  until kubectl get ns "${ns}" >/dev/null 2>&1; do
    [ "$(date +%s)" -lt "${deadline}" ] ||
      die "${ns} did not appear within ${CD_TIMEOUT}s; check the cd-tenant workflow run for $(tenant_branch "${tenant}")"
    sleep 10
  done
  ensure_pg_secret "${ns}"
  until helm -n "${ns}" status document-service >/dev/null 2>&1 &&
        kubectl -n "${ns}" get deploy document-service api-gateway auth-service >/dev/null 2>&1; do
    [ "$(date +%s)" -lt "${deadline}" ] ||
      die "${tenant} did not appear within ${CD_TIMEOUT}s; check the cd-tenant workflow run for $(tenant_branch "${tenant}")"
    sleep 15
  done
}
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  wait_for_tenant "${tenant}"
  "${REPO}/scripts/tenant-scale.sh" "${tenant}" up >/dev/null
done

# ---------- 3. tenant Postgres ----------
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  ns="$(tenant_ns "${tenant}")"
  log "Applying tenant Postgres in ${ns} (cpu limit ${POSTGRES_CPU_LIMIT})"
  render "${ONCALL_DIR}/k8s/postgres.yaml" POSTGRES_CPU_LIMIT | kubectl -n "${ns}" apply -f - >/dev/null
done
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  kubectl -n "$(tenant_ns "${tenant}")" rollout status "deploy/${PG_DEPLOY}" --timeout=5m >/dev/null ||
    die "${PG_DEPLOY} did not become ready in $(tenant_ns "${tenant}")"
done

# ---------- 4. document-service on the dedicated database ----------
for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  ns="$(tenant_ns "${tenant}")"
  db_secret="$(kubectl -n "${ns}" get deploy document-service -o json |
    jq -r '[.spec.template.spec.containers[].env[]? | select(.name == "DOC_SVC_DATABASE_URL")
            | .valueFrom.secretKeyRef.name // empty] | first // empty')"
  [ "${db_secret}" = oncall-postgres ] ||
    die "document-service in ${ns} does not take DOC_SVC_DATABASE_URL from Secret oncall-postgres; the chart or infrastructure/helm/tenant-values/${tenant}/document-service.yaml is missing database.urlSecret"
  # A pod that started before the Secret existed is stuck or on old config.
  kubectl -n "${ns}" rollout restart deploy/document-service >/dev/null
  kubectl -n "${ns}" rollout status deploy/document-service --timeout=5m >/dev/null ||
    die "document-service did not become ready on oncall-postgres in ${ns}"
  [ "$(pg "${tenant}" -At -c "SELECT to_regclass('public.documents') IS NOT NULL")" = t ] ||
    die "document-service is ready but has not migrated oncall-postgres in ${ns}"
  log "document-service in ${ns} is ready on oncall-postgres"
done

# ---------- 5. channel and platform ----------
channel_dir="${ONCALL_DIR}/channel/k8s"
if [ -f "${ONCALL_DIR}/channel/kustomization.yaml" ]; then
  log "Deploying the incident channel (kustomize incident/oncall/channel)"
  kubectl apply -k "${ONCALL_DIR}/channel" >/dev/null
elif [ -d "${channel_dir}" ]; then
  log "Deploying the incident channel (${channel_dir#"${REPO}"/})"
  kubectl -n "${PLATFORM_NS}" create configmap incident-channel-code \
    --from-file=channel.py="${ONCALL_DIR}/channel/channel.py" --dry-run=client -o yaml |
    kubectl -n "${PLATFORM_NS}" apply -f - >/dev/null
  kubectl -n "${PLATFORM_NS}" apply -f "${channel_dir}" >/dev/null
else
  die "${channel_dir#"${REPO}"/} is missing; the incident channel has not landed on this checkout"
fi
persona_env=()
[ -z "${ONCALL_SRE_USER_ID:-}" ] || persona_env+=("PERSONA_SRE_USER_ID=${ONCALL_SRE_USER_ID}")
[ -z "${ONCALL_IM_USER_ID:-}" ] || persona_env+=("PERSONA_IM_USER_ID=${ONCALL_IM_USER_ID}")
if [ "${#persona_env[@]}" -gt 0 ]; then
  kubectl -n "${PLATFORM_NS}" set env deploy/incident-channel "${persona_env[@]}" >/dev/null
else
  warn "ONCALL_SRE_USER_ID and ONCALL_IM_USER_ID are unset; channel replies stay on the page until they are set"
fi
kubectl -n "${PLATFORM_NS}" rollout status deploy/incident-channel --timeout=3m >/dev/null ||
  die "incident-channel did not become ready in ${PLATFORM_NS}"

"${ONCALL_DIR}/platform-up.sh"

log "Up. Before: https://$(web_host "${BEFORE_TENANT}")  After: https://$(web_host "${AFTER_TENANT}")"
log "Channel: https://${CHANNEL_HOST}  Next: make oncall-arm TENANT=${BEFORE_TENANT}"
