#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
NS="${ANALYTICS_CONTRACT_NS:-sfx-d1110-analytics-ci}"
make sfx-teradata-up NS="$NS" ROWS_PER_TABLE=800 >&2
VENV="$HOME/.cache/analytics-contract-venv"
if [[ ! -x "$VENV/bin/python" ]]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -r consumers/contract-kit/requirements-dev.txt >&2
fi
PORT=$(NS="$NS" python3 -c 'import os,zlib; print(54500+zlib.crc32(os.environ["NS"].encode())%1000)')
printf 'CONTRACT_ENV TD_PG_PORT=%s\n' "$PORT"
printf 'CONTRACT_ENV CONTRACT_KIT_PYTHON=%s/bin/python\n' "$VENV"
