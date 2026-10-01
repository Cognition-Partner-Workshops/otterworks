#!/usr/bin/env bash
# Install or refresh the shared platform pieces of the on-call storm (Loki,
# Alloy, Tempo, datasources, Alertmanager routes). The installer itself lives in
# incident/oncall/platform/; this wrapper only checks it is there.
#
# Usage: incident/oncall/platform-up.sh
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

installer="${ONCALL_DIR}/platform/install.sh"
[ -x "${installer}" ] || die "${installer#"${REPO}"/} is missing; the platform pieces have not landed on this checkout"
ensure_kubeconfig
log "Installing platform pieces (${installer#"${REPO}"/})"
"${installer}"
