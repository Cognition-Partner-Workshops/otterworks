#!/usr/bin/env bash
# Silence page=oncall alerts on one tenant for a few minutes, so tearing the
# fix down (alembic downgrade 004 drops the index while the worker is still on)
# does not page Devin a second time. make oncall-disarm, oncall-load and
# oncall-reset expire the silence.
#
# Usage: incident/oncall/quiet.sh <oncall-before|oncall-after> [minutes]
set -euo pipefail

# shellcheck source=incident/oncall/lib.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

require_bins kubectl jq curl
ensure_kubeconfig

[ $# -ge 1 ] || die "usage: quiet.sh <tenant> [minutes]"
tenant="$1"
minutes="${2:-15}"
ns="$(tenant_ns "${tenant}")"
id="$(am_silence_arm "${ns}" "${minutes}" "oncall quiet: tearing the fix down after the incident closed")"
[ -n "${id}" ] || die "Alertmanager did not create the silence for ${ns}"
log "page=\"oncall\" alerts in ${ns} silenced for ${minutes} min: ${id}"
