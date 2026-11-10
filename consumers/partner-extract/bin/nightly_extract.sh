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
output=${2:-partner-invoices-$extract_date.csv}
directory=$(cd -- "$(dirname -- "$output")" && pwd)
output="$directory/$(basename -- "$output")"
work=$(mktemp -d "$directory/.partner-extract.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
if [[ $work == *[\"\\$'\n'$'\r']* ]]; then
  printf '%s\n' 'warehouse export directory cannot contain quotes, backslashes or newlines' >&2
  exit 2
fi
export_file="$work/rows.csv"
export_rows() {
  if [[ -n ${WAREHOUSE_EXPORT_BIN:-} ]]; then
    "$WAREHOUSE_EXPORT_BIN" "$extract_date" "$export_file"
  else
    "${PARTNER_EXTRACT_PYTHON:-python3}" "$ROOT/bin/snowflake_export.py" "$extract_date" "$export_file"
  fi
}
export_rows || {
  printf '%s\n' 'warehouse extraction failed; no CSV published' >&2
  exit 1
}
bash "$ROOT/bin/postprocess.sh" "$export_file" "$work/partner.csv"
mv -- "$work/partner.csv" "$output"
bash "$ROOT/bin/sftp_push.sh" "$output"
printf 'Extracted %s to %s\n' "$extract_date" "$output"
