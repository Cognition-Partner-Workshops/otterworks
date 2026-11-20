#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/.." && pwd)
: "${TD_JDBC_PASSWORD:?TD_JDBC_PASSWORD is required}"
export TD_JDBC_PASSWORD
exec python3 "$root/template/submit.py" "$@"
