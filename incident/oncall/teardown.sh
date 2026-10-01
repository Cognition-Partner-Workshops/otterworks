#!/usr/bin/env bash
# Remove the on-call storm estate: both tenants (scripts/teardown-tenant.sh),
# the incident channel, and the platform pieces. The demo-* branches stay, so
# make oncall-up can bring the estate back.
#
# Usage: incident/oncall/teardown.sh [extra scripts/teardown-tenant.sh flags]
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_bins kubectl
ensure_kubeconfig

for tenant in "${BEFORE_TENANT}" "${AFTER_TENANT}"; do
  log "Tearing down ${tenant}"
  "${REPO}/scripts/teardown-tenant.sh" "${tenant}" "$@"
done

channel_dir="${ONCALL_DIR}/channel/k8s"
if [ -f "${ONCALL_DIR}/channel/kustomization.yaml" ]; then
  kubectl delete -k "${ONCALL_DIR}/channel" --ignore-not-found >/dev/null
elif [ -d "${channel_dir}" ]; then
  kubectl -n "${PLATFORM_NS}" delete -f "${channel_dir}" --ignore-not-found >/dev/null
  kubectl -n "${PLATFORM_NS}" delete configmap incident-channel-code --ignore-not-found >/dev/null
else
  warn "${channel_dir#"${REPO}"/} is missing; incident channel not removed"
fi
log "Incident channel removed"

uninstaller="${ONCALL_DIR}/platform/uninstall.sh"
if [ -x "${uninstaller}" ]; then
  "${uninstaller}"
  log "Platform pieces removed"
else
  warn "${uninstaller#"${REPO}"/} is missing; Loki, Tempo, Alloy and the oncall Alertmanager routes are still installed"
fi
rm -rf "${STATE_DIR}"
