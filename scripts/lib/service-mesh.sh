#!/usr/bin/env bash
# ------------------------------------------------------------------------------
# The shared service mesh: Istio in ambient mode, with mesh-wide STRICT mTLS.
#
# Every service in this repo talks to its neighbours over plain
# `http://<service>:<port>` cluster DNS (the *_SERVICE_URL values in the Helm
# charts, the search indexer's document/file fetches, web-app -> api-gateway).
# None of them terminates TLS itself, and giving each of the eleven services in
# eight languages its own certificate, trust store and probe configuration is
# both a lot of surface and something that drifts. Instead the cluster encrypts
# the hop: ambient mode runs one ztunnel per node that transparently wraps
# pod-to-pod traffic in mTLS (HBONE, TCP 15008) with SPIFFE identities issued
# by istiod. The PeerAuthentication in infrastructure/helm/istio-ambient/ is
# STRICT, so a meshed pod refuses plaintext from anything that is not also in
# the mesh -- the http:// URLs stay as they are and the bytes on the wire are
# TLS 1.3 with both ends authenticated.
#
# Ambient needs no sidecars and no pod restarts: enrolling a namespace is a
# label (enroll_namespace_in_mesh). Shared edge namespaces (ingress-nginx,
# monitoring) are enrolled too so what they send into the app namespaces is
# mTLS, but hold a PERMISSIVE policy because they also receive traffic from
# outside the mesh (the NLB, the monitoring Ingress).
#
# NetworkPolicies must admit TCP 15008 wherever they admit the app port, since
# that is the port meshed traffic actually arrives on (see the chart templates).
#
# Both the golden deploy (deploy-dev.sh) and the tenant baseline
# (tenant-platform-baseline.sh) install from here so the two cannot drift.
# Idempotent; safe to call on every deploy.
# ------------------------------------------------------------------------------

MESH_NAMESPACE="${MESH_NAMESPACE:-istio-system}"
ISTIO_VERSION="${ISTIO_VERSION:-1.30.5}"
ISTIO_HELM_REPO="${ISTIO_HELM_REPO:-https://istio-release.storage.googleapis.com/charts}"
# Set to the Istio platform profile when the CNI needs one (e.g. `openshift`).
# Plain EKS with the AWS VPC CNI needs none.
MESH_PLATFORM="${MESH_PLATFORM:-}"
MESH_HELM_TIMEOUT="${MESH_HELM_TIMEOUT:-10m}"
# Edge namespaces that are enrolled with a PERMISSIVE policy (see header).
MESH_EDGE_NAMESPACES="${MESH_EDGE_NAMESPACES:-${INGRESS_NAMESPACE:-ingress-nginx} monitoring}"

MESH_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MESH_MANIFEST_DIR="${MESH_MANIFEST_DIR:-${MESH_LIB_DIR}/../../infrastructure/helm/istio-ambient}"

mesh_log()  { if declare -F log  >/dev/null; then log  "$@"; else echo "[mesh] $*"; fi; }
mesh_warn() { if declare -F warn >/dev/null; then warn "$@"; else echo "[mesh] WARN: $*" >&2; fi; }

mesh_helm_install() {
  local release=$1 chart=$2
  shift 2
  helm upgrade --install "${release}" "istio/${chart}" \
    --namespace "${MESH_NAMESPACE}" --create-namespace \
    --version "${ISTIO_VERSION}" \
    --wait --timeout "${MESH_HELM_TIMEOUT}" \
    "$@" >/dev/null
}

# Label a namespace so ztunnel captures every pod in it. Running pods are
# captured in place; nothing restarts.
enroll_namespace_in_mesh() {
  local ns=$1
  kubectl label namespace "${ns}" istio.io/dataplane-mode=ambient --overwrite >/dev/null
  mesh_log "Namespace ${ns} enrolled in the ambient mesh (mTLS STRICT)."
}

# Enroll an edge namespace (one that also receives traffic from off-mesh
# sources) with a namespace-scoped PERMISSIVE policy. No-op if it does not
# exist, since monitoring is installed out of band.
enroll_edge_namespace_in_mesh() {
  local ns=$1
  if ! kubectl get namespace "${ns}" >/dev/null 2>&1; then
    mesh_log "Edge namespace ${ns} not present; skipping mesh enrolment."
    return 0
  fi
  enroll_namespace_in_mesh "${ns}"
  NAMESPACE="${ns}" envsubst '${NAMESPACE}' \
    < "${MESH_MANIFEST_DIR}/peer-authentication-edge.yaml.tpl" \
    | kubectl apply -f - >/dev/null
}

ensure_service_mesh() {
  mesh_log "Ensuring Istio ${ISTIO_VERSION} (ambient) in ${MESH_NAMESPACE}..."
  helm repo add istio "${ISTIO_HELM_REPO}" --force-update >/dev/null
  helm repo update istio >/dev/null

  local cniArgs=(--set profile=ambient)
  if [ -n "${MESH_PLATFORM}" ]; then
    cniArgs+=(--set "global.platform=${MESH_PLATFORM}")
  fi

  mesh_helm_install istio-base base --set defaultRevision=default
  mesh_helm_install istiod istiod --set profile=ambient \
    -f "${MESH_MANIFEST_DIR}/values-istiod.yaml"
  mesh_helm_install istio-cni cni "${cniArgs[@]}"
  mesh_helm_install ztunnel ztunnel \
    -f "${MESH_MANIFEST_DIR}/values-ztunnel.yaml"

  # Mesh-wide STRICT: only mTLS into any meshed pod.
  kubectl apply -f "${MESH_MANIFEST_DIR}/peer-authentication.yaml" >/dev/null
  mesh_log "Mesh-wide PeerAuthentication STRICT applied."

  local ns
  for ns in ${MESH_EDGE_NAMESPACES}; do
    enroll_edge_namespace_in_mesh "${ns}"
  done
}
