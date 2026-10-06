#!/usr/bin/env bash
# Stage the Lambda functions into .build/<name>: handler, pg8000 and the RDS CA bundle.
# Run before terraform plan/apply/destroy.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_REGION:-us-east-1}"
for fn in db_init sql_runner; do
  OUT="${HERE}/.build/${fn}"
  rm -rf "$OUT" && mkdir -p "$OUT"
  python3 -m pip install --quiet --disable-pip-version-check --no-compile --target "$OUT" -r "${HERE}/${fn}/requirements.txt"
  cp "${HERE}/${fn}/handler.py" "$OUT/"
  curl -fsSL "https://truststore.pki.rds.amazonaws.com/${REGION}/${REGION}-bundle.pem" -o "$OUT/rds-ca.pem"
  find "$OUT" -name '__pycache__' -prune -exec rm -rf {} +
  find "$OUT" -exec touch -t 202601010000 {} +
  echo "build-lambda: staged $(find "$OUT" -type f | wc -l) files in ${OUT#"$HERE"/}"
done
