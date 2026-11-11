#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
case "${WAREHOUSE_CONTRACT_TARGET:-teradata-emulator}" in
  teradata-emulator)
    if [[ -z ${TD_PG_DSN:-} && -z ${TD_PG_HOST:-} ]]; then
      printf '%s\n' 'SKIP teradata-emulator contract: set TD_PG_DSN or TD_PG_HOST for the emulator endpoint'
      exit 0
    fi
    if ! python3 -c 'import psycopg, sqlglot' > /dev/null 2>&1; then
      printf '%s\n' 'SKIP teradata-emulator contract: missing Python dependencies psycopg and/or sqlglot'
      exit 0
    fi
    ;;
  replay|snowflake-semantics)
    ;;
  snowflake)
    for key in ACCOUNT USER ROLE PRIVATE_KEY; do
      variable="SNOWFLAKE_$key"
      if [[ -z ${!variable:-} ]]; then
        printf 'SKIP snowflake contract: missing %s\n' "$variable"
        exit 0
      fi
    done
    export SNOWFLAKE_WAREHOUSE=SFX_D1110_PARITY_WH
    work=$(mktemp -d)
    trap 'rm -rf -- "$work"' EXIT
    unset WAREHOUSE_EXPORT_BIN
    SFTP_DRY_RUN=1 FINANCE_WAREHOUSE_ENABLED=true \
      bash "$ROOT/bin/nightly_extract.sh" 2026-11-09 "$work/partner.csv"
    "${PARTNER_EXTRACT_PYTHON:-python3}" "$ROOT/contract/snowflake_check.py" "$work/partner.csv" "$work"
    exit 0
    ;;
  *)
    printf '%s\n' 'unknown warehouse contract target' >&2
    exit 2
    ;;
esac
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
export TD_USER=svc_exit_parity
WAREHOUSE_EXPORT_BIN="$ROOT/contract/teradata_export.sh" SFTP_DRY_RUN=1 FINANCE_WAREHOUSE_ENABLED=true \
  bash "$ROOT/bin/nightly_extract.sh" 2026-11-09 "$work/partner.csv" > "$work/run.log"
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
print(f"PASS partner-invoices: rows={len(rows)} sums={expected['sums']}")
PY
printf '%s\n' 'PASS exact partner CSV and shared post-processing'
