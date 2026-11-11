#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
SNOWFLAKE_DATABASE=SFX_D1110_AFTER
SNOWFLAKE_SCHEMA=COMPAT
QUERY_TAG='{"run":"sfx-d1110","act":"consumers","consumer":"partner-extract"}'
target=${WAREHOUSE_CONTRACT_TARGET:-teradata-emulator}
dataset=${CONTRACT_DATASET:-fixture}
bteq_bin="$ROOT/contract/replay_bteq.sh"
case "$target" in
  teradata-emulator|replay|snowflake-semantics)
    ;;
  databricks)
    for variable in DATABRICKS_HOST DATABRICKS_TOKEN DATABRICKS_WAREHOUSE_ID; do
      if [[ -z ${!variable:-} ]]; then
        printf 'SKIP databricks contract: %s not set (live target needs Databricks secrets)\n' "$variable" >&2
        exit 0
      fi
    done
    dataset=dbx-baseline
    bteq_bin="$ROOT/bin/databricks_bteq.sh"
    ;;
  snowflake)
    for key in ACCOUNT USER ROLE WAREHOUSE PRIVATE_KEY; do
      variable="SNOWFLAKE_$key"
      if [[ -z ${!variable:-} ]]; then
        printf 'Snowflake environment not configured: missing %s\n' "$variable" >&2
        exit 1
      fi
    done
    printf 'Snowflake adapter not installed; execute sql/partner_invoice_extract.bteq SQL in %s.%s with QUERY_TAG=%s\n' \
      "$SNOWFLAKE_DATABASE" "$SNOWFLAKE_SCHEMA" "$QUERY_TAG" >&2
    exit 1
    ;;
  *)
    printf '%s\n' 'unknown warehouse contract target' >&2
    exit 2
    ;;
esac
case "$dataset" in
  fixture)
    expected="$ROOT/contract/expected"
    export PARTNER_EXTRACT_QUERY=partner-invoices
    ;;
  dbx-baseline)
    # Emulator seeded to equal cpw.dbx_d1111_before (ROWS_PER_TABLE=2000); CURRENT_DATE pinned on both paths.
    expected="$ROOT/contract/expected/dbx-baseline"
    export PARTNER_EXTRACT_QUERY=partner-invoices-dbx-baseline
    export PARTNER_EXTRACT_AS_OF_DATE=${PARTNER_EXTRACT_AS_OF_DATE:-2026-11-10}
    ;;
  *)
    printf '%s\n' 'unknown contract dataset' >&2
    exit 2
    ;;
esac
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
BTEQ_BIN="$bteq_bin" SFTP_DRY_RUN=1 FINANCE_WAREHOUSE_ENABLED=true \
  bash "$ROOT/bin/nightly_extract.sh" 2026-11-09 "$work/partner.csv" > "$work/run.log"
if [[ -n ${CONTRACT_OUTPUT:-} ]]; then cp -- "$work/partner.csv" "$CONTRACT_OUTPUT"; fi
cmp "$expected/partner-invoices.csv" "$work/partner.csv"
python3 - "$expected/partner-invoices.json" "$work/partner.csv" <<'PY'
import csv
from decimal import Decimal
import json
import sys

with open(sys.argv[1]) as source:
    expected = json.load(source)
with open(sys.argv[2], newline="") as source:
    records = list(csv.reader(source))
columns, *rows, trailer = records
assert len(rows) == expected["row_count"]
assert [row[0] for row in rows] == expected["keys"]
for column, total in expected["sums"].items():
    index = columns.index(column.lower())
    assert sum((Decimal(row[index]) for row in rows), Decimal("0")) == Decimal(total)
assert trailer == ["TRAILER", str(len(rows)), expected["sums"]["AMOUNT_DUE"]]
print(f"PASS partner-invoices: rows={len(rows)} sums={expected['sums']}")
PY
printf 'PASS exact partner CSV and shared post-processing (target=%s dataset=%s)\n' "$target" "$dataset"
