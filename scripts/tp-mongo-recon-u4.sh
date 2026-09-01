#!/usr/bin/env bash
# U4 fixture recon: official harness engine via the D13 DynamoDB source adapter extension.
# result.json under .migration/recon/U4/gate/ is the only merge authority.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
PYTHON="${PYTHON:-/home/ubuntu/.venvs/recon/bin/python}"
[[ -x "$PYTHON" ]] || PYTHON=python3
OUT="${1:-.migration/recon/U4/gate}"

if [[ ! -v MONGODB_ATLAS_URI ]]; then
  echo "ERROR: MONGODB_ATLAS_URI must be set in the environment (by name)" >&2
  exit 2
fi
export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4566}"

rm -rf "$OUT"
set +e
"$PYTHON" .migration/recon_ext/run_dynamo_recon.py \
  --unit U4 \
  --mapping .migration/03_mapping_spec.json \
  --tolerances .migration/02_tolerances.json \
  --canonicalization .migration/canonicalization.json \
  --mode live \
  --source-endpoint-secret AWS_ENDPOINT_URL \
  --target-uri-secret MONGODB_ATLAS_URI \
  --target-db ow_tp_mongodb_205236 \
  --seed 714559852 \
  --param batch_no=85559852 \
  --param source_ns=demo \
  --out "$OUT"
rc=$?
set -e

verdict=MISSING
[[ -f "$OUT/result.json" ]] && verdict="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "$OUT/result.json")"
printf 'U4 | %s | rc=%s\n' "$verdict" "$rc"
[[ "$rc" -eq 0 && "$verdict" == "PASS" ]]
