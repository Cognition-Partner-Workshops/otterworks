#!/usr/bin/env bash
# Usage: migration/billing/scripts/atlas-scope-check.sh --db ow_tp_billing_<run> [--out <path>]
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --no-project --with pymongo==4.10.1 "$HERE/atlas_scope_check.py" "$@"
