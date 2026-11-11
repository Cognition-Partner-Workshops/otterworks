#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec "${CONTRACT_KIT_PYTHON:-python3}" "$ROOT/contract/warehouse_bteq.py" "$@"
