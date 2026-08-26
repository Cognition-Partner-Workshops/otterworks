#!/usr/bin/env bash
# Run the MongoDB showcase tool with its pinned driver, outside the app venvs.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# oracledb comes from the migration units this imports for their validators
exec uv run --no-project --with 'pymongo[srv]==4.10.1' --with oracledb==2.5.1 \
  "$REPO_ROOT/scripts/tp_mongo/showcase.py" "$@"
