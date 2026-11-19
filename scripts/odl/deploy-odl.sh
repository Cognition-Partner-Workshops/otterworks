#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ID="${1:?Usage: deploy-odl.sh ID --mode before|after}"
shift
MODE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode) MODE="${2:?mode required}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ "$ID" =~ ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ && ${#ID} -le 31 && "$ID" != main ]] || { echo "Invalid tenant ID" >&2; exit 2; }
[[ "$MODE" = before || "$MODE" = after ]] || { echo "Mode must be before or after" >&2; exit 2; }
export DB_PASSWORD
DB_PASSWORD="$(kubectl -n otterworks-platform get secret demo-ops-dashboard -o jsonpath='{.data.DB_PASSWORD}' | base64 -d)"
[ -n "$DB_PASSWORD" ] || { echo "Database password is unavailable" >&2; exit 1; }
export HELM_POST_RENDERER="${ROOT}/scripts/odl/helm-labels.py"
export ODL_TENANT_ID="$ID" ODL_MODE="$MODE"
export REPO_ROOT="$ROOT"
source "${ROOT}/scripts/lib/tenant-common.sh"
load_infra_outputs
export ODL_RDS_HOST="$RDS_HOST" ODL_RDS_PORT="$RDS_PORT" DB_USER
[ -n "$ODL_RDS_HOST" ] || { echo "RDS endpoint unavailable" >&2; exit 1; }
start=$SECONDS
source "${ROOT}/demo-platform/lib/control-common.sh"
ctl_register_run_tenant "$ID" "${ODL_CONTROL_BRANCH:-$(git -C "$ROOT" branch --show-current)}" odl-1795112287
trap 'rc=$?; if [ "$rc" -ne 0 ]; then ctl_update_status "$ID" error || true; fi' EXIT
"${ROOT}/scripts/deploy-tenant.sh" "$ID" --profile core --host-suffix demo.otterworks.app --ttl never &
core_pid=$!
python3 "${ROOT}/scripts/odl/install-sources.py" &
sources_pid=$!
rc=0
wait "$core_pid" || rc=1
wait "$sources_pid" || rc=1
if [ "$rc" -ne 0 ]; then exit "$rc"; fi
NS="otterworks-${ID}"
for service in redis meilisearch; do
  kubectl -n "$NS" patch deployment "$service" --type=merge -p \
    '{"spec":{"template":{"metadata":{"labels":{"run_token":"odl-1795112287"}}}}}'
done
kubectl -n "$NS" rollout status deployment --timeout=120s
kubectl -n "$NS" label deploy,sts,svc,ingress,secret,cm,job,cronjob,networkpolicy,resourcequota,limitrange,sa,role,rolebinding,pod,replicaset --all run_token=odl-1795112287 --overwrite >/dev/null
kubectl label namespace "$NS" run_token=odl-1795112287 --overwrite >/dev/null
if [ "$MODE" = after ] && [ -d "${ROOT}/services/operational-data-layer/deploy" ]; then
  if [ "$ID" = odl ]; then
    "${ROOT}/scripts/odl/deploy-odl-ui.sh" "$ID"
  fi
  helm upgrade --install operational-data-layer "${ROOT}/services/operational-data-layer/deploy" -n "$NS" \
    --post-renderer "$HELM_POST_RENDERER" --labels run_token=odl-1795112287 --wait --timeout 3m
fi
ctl_set_active "$ID" "https://t-${ID}.demo.otterworks.app" "https://api-t-${ID}.demo.otterworks.app" \
  "$(tenant_db_name "$ID")" "$NS" "$(( $(ctl_now) + 315360000 ))"
ctl_audit "$ID" deploy_ok "ODL ${MODE}: run_token=odl-1795112287"
echo "ODL ${MODE} deployment complete in $((SECONDS-start)) seconds"
