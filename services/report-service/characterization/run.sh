#!/usr/bin/env bash
# Runs the characterization suite against a running report-service.
#   REPORT_SERVICE_URL=http://localhost:8091 ./characterization/run.sh
set -euo pipefail
cd "$(dirname "$0")"
export REPORT_SERVICE_URL="${REPORT_SERVICE_URL:-http://localhost:8091}"
exec uv run --no-project --python 3.12 --with pytest==8.3.5 pytest -v -p no:cacheprovider test_characterization.py "$@"
