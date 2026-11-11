#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
export WAREHOUSE_EXPORT_BIN="$ROOT/tests/fake_export.sh"
export EXPORT_CAPTURE="$work/captured.args"
export RAW_FIXTURE="$ROOT/tests/fixtures/rows.csv"
export FINANCE_WAREHOUSE_ENABLED=true SFTP_DRY_RUN=1
export SFTP_KEY_PATH=/fake/keys/unit_partner
export SFTP_REMOTE_DIR=/incoming
unset FAKE_EXPORT_FAIL
bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/partner.csv" > "$work/run.log"
cmp "$ROOT/tests/fixtures/expected.csv" "$work/partner.csv"
[[ $(head -n 1 "$EXPORT_CAPTURE") == 2026-01-05 ]]
[[ $(wc -l < "$EXPORT_CAPTURE") == 2 ]]
[[ $(tail -n 1 "$EXPORT_CAPTURE") == "$work"/.partner-extract.*/rows.csv ]]
grep -Fq 'sftp -i /fake/keys/unit_partner -b - partner@sftp.partner.example' "$work/run.log"
grep -Fq "put \"$work/partner.csv\" \"/incoming/partner.csv\"" "$work/run.log"
printf '%s\n' 'PASS populated CSV, exact totals, date substitution and SFTP batch'

bash "$ROOT/bin/nightly_extract.sh" 2024-02-29 "$work/leap.csv" > /dev/null
[[ $(head -n 1 "$EXPORT_CAPTURE") == 2024-02-29 ]]
(
  cd "$work"
  bash "$ROOT/bin/nightly_extract.sh" > /dev/null
)
yesterday=$(date -u -d yesterday +%F)
[[ -f "$work/partner-invoices-$yesterday.csv" ]]
[[ $(head -n 1 "$EXPORT_CAPTURE") == "$yesterday" ]]
printf '%s\n' 'PASS leap-day and default-yesterday dates'

: > "$work/empty.csv"
RAW_FIXTURE="$work/empty.csv" bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/empty-output.csv" > /dev/null
[[ $(wc -l < "$work/empty-output.csv") == 2 ]]
grep -Fxq 'TRAILER,0,0.00' "$work/empty-output.csv"
printf '%s\n' 'PASS empty export'

for invalid in 2026-02-30 2026-1-05 '2026-01-05;quit' 2019-12-31; do
  if bash "$ROOT/bin/nightly_extract.sh" "$invalid" "$work/invalid.csv" > /dev/null 2>&1; then exit 1; fi
done
[[ ! -e "$work/invalid.csv" ]]
FINANCE_WAREHOUSE_ENABLED=false bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/disabled.csv" > /dev/null
[[ ! -e "$work/disabled.csv" ]]
printf '%s\n' 'PASS invalid dates and disabled flag'

cp "$work/partner.csv" "$work/original.csv"
if FAKE_EXPORT_FAIL=1 bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/partner.csv" > /dev/null 2>&1; then exit 1; fi
cmp "$work/original.csv" "$work/partner.csv"
printf '%s\n' 'not,valid,report' > "$work/bad.csv"
if RAW_FIXTURE="$work/bad.csv" bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/partner.csv" > /dev/null 2>&1; then exit 1; fi
cmp "$work/original.csv" "$work/partner.csv"
if SFTP_DRY_RUN=0 bash "$ROOT/bin/sftp_push.sh" "$work/partner.csv" > /dev/null 2>&1; then exit 1; fi
printf '%s\n' 'PASS exporter/malformed-report failures preserve output; live SFTP refused'

printf '%s\n' 'INV-2026-004814,A000318274,2026-01-05,-0.10,0.00,-0.10,USD' > "$work/credit.csv"
bash "$ROOT/bin/postprocess.sh" "$work/credit.csv" "$work/credit-output.csv"
grep -Fxq 'TRAILER,1,-0.10' "$work/credit-output.csv"
printf '%s\n' 'INV-2026-004814,ACC-0000001,2026-01-05,.10,.00,-.10,USD' > "$work/fraction.csv"
bash "$ROOT/bin/postprocess.sh" "$work/fraction.csv" "$work/fraction-output.csv"
grep -Fxq 'INV-2026-004814,ACC-0000001,2026-01-05,0.10,0.00,-0.10,USD' "$work/fraction-output.csv"
for row in \
  'INV-2026-004814,A000318274,2026-01-05,1.001,0.00,0.00,USD' \
  'INV-2026-004814,A000318274,2026-01-05,999999999999.00,0.00,0.00,USD'; do
  printf '%s\n' "$row" > "$work/bad.csv"
  if bash "$ROOT/bin/postprocess.sh" "$work/bad.csv" "$work/rejected.csv" > /dev/null 2>&1; then exit 1; fi
done
cat "$RAW_FIXTURE" "$RAW_FIXTURE" > "$work/duplicates.csv"
if bash "$ROOT/bin/postprocess.sh" "$work/duplicates.csv" "$work/rejected.csv" > /dev/null 2>&1; then exit 1; fi
printf '%s\n' 'PASS credits, decimal validation, overflow guard and duplicate rejection'
if grep -ERiq 'svc_partner_sftp|\.LOGON|bteq' "$ROOT/bin" "$ROOT/sql"; then exit 1; fi
python3 - "$ROOT" <<'PY'
from pathlib import Path
import re
import sys
sql = (Path(sys.argv[1]) / "sql/partner_invoice_extract.sql").read_text()
assert "%(extract_date)s" in sql
objects = re.findall(r"\b(?:FROM|JOIN)\s+([\w.]+)", sql, re.I)
assert {obj for obj in objects if "." in obj} == {
    "SFX_D1110_AFTER.COMPAT.CUSTOMER_ACCOUNT",
    "SFX_D1110_AFTER.COMPAT.INVOICE_HDR",
    "SFX_D1110_AFTER.COMPAT.PAYMENT",
}
assert all(obj in {"invoice_base", "invoices"} or obj.startswith("SFX_D1110_AFTER.COMPAT.") for obj in objects)
PY
if env -u SNOWFLAKE_ACCOUNT -u SNOWFLAKE_USER -u SNOWFLAKE_ROLE -u SNOWFLAKE_PRIVATE_KEY -u SNOWFLAKE_WAREHOUSE \
  python3 "$ROOT/bin/snowflake_export.py" 2026-01-05 "$work/no-env.csv" > "$work/no-env.log" 2>&1; then exit 1; fi
grep -Fq 'missing SNOWFLAKE_ACCOUNT' "$work/no-env.log"
env -u SNOWFLAKE_ACCOUNT WAREHOUSE_CONTRACT_TARGET=snowflake bash "$ROOT/contract/run.sh" > "$work/skip.log"
grep -Fxq 'SKIP snowflake contract: missing SNOWFLAKE_ACCOUNT' "$work/skip.log"
printf '%s\n' 'PASS Snowflake SQL scope, missing credentials and contract skip'
python3 "$ROOT/tests/test_snowflake_export.py"
python3 "$ROOT/tests/test_default_date.py"
python3 "$ROOT/tests/test_contract_runtime.py"
printf '%s\n' 'All partner-extract unit tests passed'
