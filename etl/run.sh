#!/bin/bash
# ETL runner — sets up environment and runs the specified script
# Usage: ./run.sh <script_name.py>
# ETL_S3_BUCKET_OWNER must be set (12-digit account id owning the ETL buckets).
set -euo pipefail
ETL_HOME="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ETL_HOME/scripts${PYTHONPATH:+:$PYTHONPATH}"
export ETL_CONFIG_PATH="${ETL_CONFIG_PATH:-$ETL_HOME/config.ini}"
exec python3 "$ETL_HOME/scripts/run_job.py" "$@"
