#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
SNOWFLAKE_DATABASE=SFX_D1110_AFTER
SNOWFLAKE_SCHEMA=COMPAT
QUERY_TAG='{"run":"sfx-d1110","act":"consumers","consumer":"partner-extract"}'
case "${WAREHOUSE_CONTRACT_TARGET:-teradata-emulator}" in
  teradata-emulator)
    if [[ -n ${TD_EMULATOR_URL:-} ]]; then
      printf '%s\n' 'emulator endpoint not configured' >&2
      exit 1
    fi
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
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
BTEQ_BIN="$ROOT/contract/replay_bteq.sh" SFTP_DRY_RUN=1 FINANCE_WAREHOUSE_ENABLED=true \
  bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/partner.csv" > "$work/run.log"
cmp "$ROOT/contract/expected/partner-invoices.csv" "$work/partner.csv"
python3 - "$ROOT/contract/expected/partner-invoices.json" "$work/partner.csv" <<'PY'
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
print("PASS partner-invoices: rows=2 AMOUNT_DUE=1410.75 TAX_AMT=110.75 OPEN_BALANCE=610.75")
PY
printf '%s\n' 'PASS exact partner CSV and shared post-processing; recorded Teradata replay'
