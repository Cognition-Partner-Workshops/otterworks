#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

if [[ ${FINANCE_WAREHOUSE_ENABLED:-true} != true ]]; then
  printf '%s\n' 'finance warehouse is disabled'
  exit 0
fi
if (( $# > 2 )); then
  printf '%s\n' 'usage: nightly_extract.sh [YYYY-MM-DD] [output.csv]' >&2
  exit 2
fi
extract_date=${1:-$(date -d yesterday +%F)}
if [[ ! $extract_date =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] ||
   ! normalized=$(date -d "$extract_date" +%F 2>/dev/null) ||
   [[ $normalized != "$extract_date" || $extract_date < 2020-01-01 ]]; then
  printf '%s\n' 'extract date must be a valid YYYY-MM-DD on or after 2020-01-01' >&2
  exit 2
fi
year=${extract_date:0:4}
month=${extract_date:5:2}
day=${extract_date:8:2}
date_int=$(( (10#$year - 1900) * 10000 + 10#$month * 100 + 10#$day ))
output=${2:-partner-invoices-$extract_date.csv}
directory=$(cd -- "$(dirname -- "$output")" && pwd)
output="$directory/$(basename -- "$output")"
work=$(mktemp -d "$directory/.partner-extract.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
if [[ $work == *[\"\\$'\n'$'\r']* ]]; then
  printf '%s\n' 'BTEQ export directory cannot contain quotes, backslashes or newlines' >&2
  exit 2
fi
export_file="$work/rows.csv"
escaped_export=${export_file//&/\\&}
escaped_export=${escaped_export//|/\\|}
sed -e "s|@EXTRACT_DATE_INT@|$date_int|g" \
    -e "s|@EXPORT_FILE@|$escaped_export|g" \
    "$ROOT/sql/partner_invoice_extract.bteq" > "$work/extract.bteq"
"${BTEQ_BIN:-bteq}" < "$work/extract.bteq" > "$work/bteq.log" 2>&1 || {
  printf '%s\n' 'BTEQ extraction failed; no CSV published' >&2
  exit 1
}
bash "$ROOT/bin/postprocess.sh" "$export_file" "$work/partner.csv"
mv -- "$work/partner.csv" "$output"
bash "$ROOT/bin/sftp_push.sh" "$output"
printf 'Extracted %s to %s\n' "$extract_date" "$output"
