#!/usr/bin/env bash
# Run the pytest suite (etl/airflow/tests) inside the built Airflow image, so tests see the
# exact Airflow, provider and Python versions that run the DAGs. The source tree is mounted
# read-only; pytest is installed against the image's own Airflow constraints file.
# The legacy etl/crontab is mounted read-only so the schedule map can be checked against it.
# The S3 staging roundtrip runs against LocalStack on otterworks-network when its health
# endpoint answers. Setting OTTERWORKS_LOCALSTACK_URL (as CI does) makes LocalStack required:
# the run fails if it is unreachable instead of skipping the roundtrip.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${AIRFLOW_IMAGE:-otterworks/etl-airflow:local}"
NETWORK="${AIRFLOW_TEST_NETWORK:-otterworks-network}"
LOCALSTACK_REQUIRED="${OTTERWORKS_LOCALSTACK_URL:+1}"
LOCALSTACK_URL="${OTTERWORKS_LOCALSTACK_URL-http://localstack:4566}"

net_args=()
if docker network inspect "$NETWORK" >/dev/null 2>&1; then
  net_args=(--network "$NETWORK")
elif [[ -n "$LOCALSTACK_REQUIRED" ]]; then
  echo "run-tests: OTTERWORKS_LOCALSTACK_URL is set but network $NETWORK does not exist" >&2
  exit 1
else
  LOCALSTACK_URL=""
fi

exec docker run --rm "${net_args[@]}" \
  -v "$ROOT:/opt/otterworks-etl:ro" -w /opt/otterworks-etl \
  -v "$ROOT/../crontab:/opt/legacy/crontab:ro" -e OTTERWORKS_LEGACY_CRONTAB=/opt/legacy/crontab \
  -e OTTERWORKS_LOCALSTACK_URL="$LOCALSTACK_URL" -e LOCALSTACK_REQUIRED="$LOCALSTACK_REQUIRED" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint bash "$IMAGE" -c '
    set -euo pipefail
    af="$(python -c "import airflow; print(airflow.__version__)")"
    py="$(python -c "import sys; print(f\"{sys.version_info[0]}.{sys.version_info[1]}\")")"
    pip install --quiet --no-cache-dir \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${af}/constraints-${py}.txt" \
      -r tests/requirements.txt
    if [[ -n "$OTTERWORKS_LOCALSTACK_URL" ]] && ! python -c "import sys, urllib.request; urllib.request.urlopen(sys.argv[1] + \"/_localstack/health\", timeout=5)" "$OTTERWORKS_LOCALSTACK_URL" 2>/dev/null; then
      if [[ -n "$LOCALSTACK_REQUIRED" ]]; then
        echo "run-tests: LocalStack is not reachable at $OTTERWORKS_LOCALSTACK_URL" >&2
        exit 1
      fi
      echo "run-tests: LocalStack is not reachable at $OTTERWORKS_LOCALSTACK_URL; skipping the S3 roundtrip" >&2
      export OTTERWORKS_LOCALSTACK_URL=""
    fi
    python -m pytest -p no:cacheprovider -ra "$@"
  ' run-tests "${@:-tests}"
