#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# Unit tests for the shared service mesh helper.
#
# The mesh is what turns the services' plain http:// calls into mTLS on the
# wire, so a regression here (a chart not installed, the STRICT policy not
# applied, a namespace not enrolled, a NetworkPolicy that drops the HBONE
# port) silently puts cluster traffic back in clear text while every deploy
# still reports success.
#
# helm / kubectl are stubbed; this runs anywhere.
# ------------------------------------------------------------------------------
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); echo "  ok   - $1"; }
nope() { FAIL=$((FAIL+1)); echo "  FAIL - $1"; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else nope "$1 (expected '$3', got '$2')"; fi; }
contains() { if grep -q -- "$3" <<<"$2"; then ok "$1"; else nope "$1 (missing '$3')"; fi; }

# ---- stubs -------------------------------------------------------------------
# The stubs run inside the helper's pipelines (subshells), so they record to
# files rather than variables.
CALLS_FILE="$(mktemp)"; APPLIED_FILE="$(mktemp)"
trap 'rm -f "${CALLS_FILE}" "${APPLIED_FILE}"' EXIT
EXISTING_NAMESPACES="ingress-nginx"
helm() { echo "helm $*" >>"${CALLS_FILE}"; }
kubectl() {
  echo "kubectl $*" >>"${CALLS_FILE}"
  case "$1 $2" in
    "get namespace") grep -qw -- "$3" <<<"${EXISTING_NAMESPACES}" ;;
    "apply -f") { cat; echo "---"; } >>"${APPLIED_FILE}" ;;
    *) return 0 ;;
  esac
}
reset() { : >"${CALLS_FILE}"; : >"${APPLIED_FILE}"; }
calls() { cat "${CALLS_FILE}"; }
applied() { cat "${APPLIED_FILE}"; }

# shellcheck source=service-mesh.sh
source "${SCRIPT_DIR}/service-mesh.sh"

echo "ensure_service_mesh"
reset
ensure_service_mesh >/dev/null

for chart in base istiod cni ztunnel; do
  contains "installs istio/${chart} pinned to ${ISTIO_VERSION}" "$(calls)" \
    "helm upgrade --install .* istio/${chart} --namespace istio-system .*--version ${ISTIO_VERSION} "
done
contains "istiod uses the ambient profile" "$(calls)" "istio/istiod .*--set profile=ambient"
contains "cni uses the ambient profile"    "$(calls)" "istio/cni .*--set profile=ambient"
contains "waits for every chart" "$(calls)" "istio/ztunnel .*--wait"
check "mesh-wide PeerAuthentication applied" \
  "$(grep -c "apply -f .*istio-ambient/peer-authentication.yaml" <<<"$(calls)")" "1"
check "mesh-wide policy is STRICT" \
  "$(grep -A1 "mtls:" "${MESH_MANIFEST_DIR}/peer-authentication.yaml" | grep -c "mode: STRICT")" "1"
check "mesh-wide policy lives in the root namespace" \
  "$(grep -c "namespace: istio-system" "${MESH_MANIFEST_DIR}/peer-authentication.yaml")" "1"
contains "present edge namespace is enrolled" "$(calls)" \
  "kubectl label namespace ingress-nginx istio.io/dataplane-mode=ambient"
contains "present edge namespace gets a PERMISSIVE policy" "$(applied)" "namespace: ingress-nginx"
contains "edge policy is PERMISSIVE, not STRICT" "$(applied)" "mode: PERMISSIVE"
if grep -q "label namespace monitoring" <<<"$(calls)"; then
  nope "absent edge namespace is skipped"
else
  ok "absent edge namespace is skipped"
fi

echo "enroll_namespace_in_mesh"
reset
enroll_namespace_in_mesh otterworks-abc >/dev/null
contains "labels the namespace for ambient capture" "$(calls)" \
  "kubectl label namespace otterworks-abc istio.io/dataplane-mode=ambient --overwrite"
if grep -q "PERMISSIVE" <<<"$(applied)"; then
  nope "app namespaces stay under the STRICT mesh-wide policy"
else
  ok "app namespaces stay under the STRICT mesh-wide policy"
fi

echo "deploy scripts enroll their namespaces"
contains "deploy-dev.sh installs the mesh" "$(cat "${REPO_ROOT}/scripts/deploy-dev.sh")" "^ensure_service_mesh$"
contains "deploy-dev.sh enrolls the golden namespace" "$(cat "${REPO_ROOT}/scripts/deploy-dev.sh")" \
  'enroll_namespace_in_mesh "${NAMESPACE}"'
contains "tenant baseline installs the mesh" "$(cat "${REPO_ROOT}/scripts/tenant-platform-baseline.sh")" "^ensure_service_mesh$"
contains "deploy-tenant.sh enrolls the tenant namespace" "$(cat "${REPO_ROOT}/scripts/deploy-tenant.sh")" \
  "istio.io/dataplane-mode: ambient"

echo "NetworkPolicies admit HBONE (15008) wherever they admit an application port"
for np in "${REPO_ROOT}"/infrastructure/helm/*/templates/networkpolicy.yaml; do
  chart="$(basename "$(dirname "$(dirname "${np}")")")"
  grep -q "port: {{" "${np}" || continue
  check "${chart}" "$(grep -c "port: 15008" "${np}" | awk '$1 > 0 {print "yes"} $1 == 0 {print "no"}')" "yes"
done

echo
echo "${PASS} passed, ${FAIL} failed"
[ "${FAIL}" -eq 0 ]
