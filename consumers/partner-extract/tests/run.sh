#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
export BTEQ_BIN="$ROOT/tests/fake_bteq.sh"
export BTEQ_CAPTURE="$work/captured.bteq"
export RAW_FIXTURE="$ROOT/tests/fixtures/rows.csv"
export FINANCE_WAREHOUSE_ENABLED=true SFTP_DRY_RUN=1
export SFTP_KEY_PATH=/fake/keys/unit_partner
export SFTP_REMOTE_DIR=/incoming
unset FAKE_BTEQ_FAIL
bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/partner.csv" > "$work/run.log"
cmp "$ROOT/tests/fixtures/expected.csv" "$work/partner.csv"
grep -Fq 'WHERE h.BILL_DT = 1260105' "$BTEQ_CAPTURE"
grep -Fq 'CURRENT_DATE - 1' "$BTEQ_CAPTURE"
if grep -Eq '@(EXPORT_FILE|EXTRACT_DATE_INT)@' "$BTEQ_CAPTURE"; then exit 1; fi
grep -Fq 'sftp -i /fake/keys/unit_partner -b - partner@sftp.partner.example' "$work/run.log"
grep -Fq "put \"$work/partner.csv\" \"/incoming/partner.csv\"" "$work/run.log"
printf '%s\n' 'PASS populated CSV, exact totals, date substitution and SFTP batch'

bash "$ROOT/bin/nightly_extract.sh" 2024-02-29 "$work/leap.csv" > /dev/null
grep -Fq 'WHERE h.BILL_DT = 1240229' "$BTEQ_CAPTURE"
(
  cd "$work"
  bash "$ROOT/bin/nightly_extract.sh" > /dev/null
)
yesterday=$(date -d yesterday +%F)
[[ -f "$work/partner-invoices-$yesterday.csv" ]]
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
if FAKE_BTEQ_FAIL=1 bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/partner.csv" > /dev/null 2>&1; then exit 1; fi
cmp "$work/original.csv" "$work/partner.csv"
printf '%s\n' 'not,valid,report' > "$work/bad.csv"
if RAW_FIXTURE="$work/bad.csv" bash "$ROOT/bin/nightly_extract.sh" 2026-01-05 "$work/partner.csv" > /dev/null 2>&1; then exit 1; fi
cmp "$work/original.csv" "$work/partner.csv"
if SFTP_DRY_RUN=0 bash "$ROOT/bin/sftp_push.sh" "$work/partner.csv" > /dev/null 2>&1; then exit 1; fi
printf '%s\n' 'PASS BTEQ/malformed-report failures preserve output; live SFTP refused'

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
printf '%s\n' 'All partner-extract unit tests passed'
