#!/usr/bin/env bash
# Stage the Lambda functions into .build/<name>: handler, dependencies and the RDS CA bundle.
# billing_service also gets services/billing-service/{app,db} and wheels built for the
# python3.12/x86_64 Lambda runtime. Run before terraform plan/apply/destroy.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="${HERE}/../../../services/billing-service"
REGION="${AWS_REGION:-us-east-1}"
for fn in db_init sql_runner billing_service; do
  OUT="${HERE}/.build/${fn}"
  rm -rf "$OUT" && mkdir -p "$OUT"
  if [ "$fn" = billing_service ]; then
    python3 -m pip install --quiet --disable-pip-version-check --no-compile --target "$OUT" \
      --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all: \
      -r "${HERE}/${fn}/requirements.txt"
    cp -R "${SERVICE}/app" "${SERVICE}/db" "$OUT/"
  else
    python3 -m pip install --quiet --disable-pip-version-check --no-compile --target "$OUT" -r "${HERE}/${fn}/requirements.txt"
  fi
  cp "${HERE}/${fn}/handler.py" "$OUT/"
  curl -fsSL "https://truststore.pki.rds.amazonaws.com/${REGION}/${REGION}-bundle.pem" -o "$OUT/rds-ca.pem"
  find "$OUT" -name '__pycache__' -prune -exec rm -rf {} +
  find "$OUT" -exec touch -t 202601010000 {} +
  echo "build-lambda: staged $(find "$OUT" -type f | wc -l) files in ${OUT#"$HERE"/}"
done
