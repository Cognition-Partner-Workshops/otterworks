#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec "${SFX_VENV:-$ROOT/warehouse/snowflake/.venv}/bin/python" "$ROOT/warehouse/pipeline/break_upstream.py"
