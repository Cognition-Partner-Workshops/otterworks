#!/usr/bin/env bash
# Stage the db-init function into .build/db_init: handler, pg8000 and the RDS CA bundle.
# Run before terraform plan/apply/destroy.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${HERE}/.build/db_init"
REGION="${AWS_REGION:-us-east-1}"
rm -rf "$OUT" && mkdir -p "$OUT"
python3 -m pip install --quiet --disable-pip-version-check --no-compile --target "$OUT" -r "${HERE}/db_init/requirements.txt"
cp "${HERE}/db_init/handler.py" "$OUT/"
curl -fsSL "https://truststore.pki.rds.amazonaws.com/${REGION}/${REGION}-bundle.pem" -o "$OUT/rds-ca.pem"
find "$OUT" -name '__pycache__' -prune -exec rm -rf {} +
find "$OUT" -exec touch -t 202601010000 {} +
echo "build-lambda: staged $(find "$OUT" -type f | wc -l) files in ${OUT#"$HERE"/}"
