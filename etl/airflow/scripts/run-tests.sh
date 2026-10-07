#!/usr/bin/env bash
# Run the pytest suite (etl/airflow/tests) inside the built Airflow image, so tests see the
# exact Airflow, provider and Python versions that run the DAGs. The source tree is mounted
# read-only; pytest is installed against the image's own Airflow constraints file.
# The pre-cutover crontab (etl/legacy-cron/crontab.pre-cutover) is mounted read-only so the
# schedule map can be checked against it.
# With LocalStack up on otterworks-network the S3 staging roundtrip runs against it too.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${AIRFLOW_IMAGE:-otterworks/etl-airflow:local}"
NETWORK="${AIRFLOW_TEST_NETWORK:-otterworks-network}"
LOCALSTACK_URL="${OTTERWORKS_LOCALSTACK_URL-http://localstack:4566}"

net_args=()
if docker network inspect "$NETWORK" >/dev/null 2>&1; then
  net_args=(--network "$NETWORK")
else
  LOCALSTACK_URL=""
fi

exec docker run --rm "${net_args[@]}" \
  -v "$ROOT:/opt/otterworks-etl:ro" -w /opt/otterworks-etl \
  -v "$ROOT/../legacy-cron/crontab.pre-cutover:/opt/legacy/crontab:ro" -e OTTERWORKS_LEGACY_CRONTAB=/opt/legacy/crontab \
  -e OTTERWORKS_LOCALSTACK_URL="$LOCALSTACK_URL" \
  -e PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint bash "$IMAGE" -c '
    set -euo pipefail
    af="$(python -c "import airflow; print(airflow.__version__)")"
    py="$(python -c "import sys; print(f\"{sys.version_info[0]}.{sys.version_info[1]}\")")"
    pip install --quiet --no-cache-dir \
      --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-${af}/constraints-${py}.txt" \
      -r tests/requirements.txt
    python -m pytest -p no:cacheprovider -ra "$@"
  ' run-tests "${@:-tests}"
