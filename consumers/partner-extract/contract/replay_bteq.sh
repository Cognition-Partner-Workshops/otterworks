#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
input=$(cat)
export_file=$(printf '%s\n' "$input" | sed -n 's/^\.EXPORT REPORT FILE="\(.*\)"$/\1/p')
[[ -n $export_file ]]
expected=$(sed -e 's|@EXTRACT_DATE_INT@|1260105|g' \
  -e "s|@EXPORT_FILE@|$export_file|g" "$ROOT/sql/partner_invoice_extract.bteq")
[[ $input == "$expected" ]] || { printf '%s\n' 'replay received unexpected BTEQ query' >&2; exit 1; }
python3 - "$ROOT/contract/recorded/teradata/partner-invoices.json" "$export_file" <<'PY'
import csv
import json
import sys

with open(sys.argv[1]) as source:
    recorded = json.load(source)
with open(sys.argv[2], "w", newline="") as destination:
    csv.writer(destination, lineterminator="\n").writerows(recorded["rows"])
PY
