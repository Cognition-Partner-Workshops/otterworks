#!/usr/bin/env bash
# U4 fixture recon: official harness engine via the D13 DynamoDB source adapter extension.
# result.json under .migration/recon/U4/gate/ is the only merge authority. The run writes to
# a scratch directory and replaces the gate only once a complete result.json exists, so a
# failed or aborted run can never erase the last evidence (its output is kept in *.failed).
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
if [[ ! -v AWS_ENDPOINT_URL ]]; then
  echo "ERROR: AWS_ENDPOINT_URL must name the DynamoDB endpoint (fixture: http://localhost:4566)" >&2
  exit 2
fi
if ! "$PYTHON" -c 'import recon.engine, pymongo, boto3' 2>/dev/null; then
  echo "ERROR: $PYTHON cannot import the recon harness (pip install -e <harness> pymongo boto3)" >&2
  exit 2
fi

SCRATCH="${OUT%/}.tmp"
rm -rf "$SCRATCH" "${OUT%/}.failed"
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
  --out "$SCRATCH"
rc=$?
set -e

if [[ ! -f "$SCRATCH/result.json" ]]; then
  [[ -d "$SCRATCH" ]] && mv "$SCRATCH" "${OUT%/}.failed"
  printf 'U4 | MISSING | rc=%s (previous gate retained)\n' "$rc"
  exit 1
fi
rm -rf "$OUT"
mv "$SCRATCH" "$OUT"
verdict="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "$OUT/result.json")"
printf 'U4 | %s | rc=%s\n' "$verdict" "$rc"
[[ "$rc" -eq 0 && "$verdict" == "PASS" ]]
