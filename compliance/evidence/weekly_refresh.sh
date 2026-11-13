#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$ROOT"
export PATH="$HOME/bin:$HOME/.local/bin:$PATH"
source compliance/evidence/provision_deps.sh
exec python3 compliance/evidence/weekly_refresh.py "$@"
