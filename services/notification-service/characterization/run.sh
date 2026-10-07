#!/usr/bin/env bash
# Run the characterization suite against a running notification-service.
#   BASE_URL=http://localhost:8086 AWS_ENDPOINT=http://localhost:4566 ./run.sh
set -euo pipefail
cd "$(dirname "$0")"
exec python3 test_characterization.py "$@"
