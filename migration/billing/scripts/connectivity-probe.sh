#!/usr/bin/env bash
# Usage: migration/billing/scripts/connectivity-probe.sh --db ow_tp_billing_<run> [--mode auto|online] [--preflight .tp-preflight/atlas-capabilities.json] [--out <path>]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --no-project --with oracledb==2.5.1 --with pymongo==4.10.1 --with requests==2.32.3 "$HERE/connectivity_probe.py" "$@"
