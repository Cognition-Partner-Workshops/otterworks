#!/usr/bin/env bash
set -euo pipefail
if (( $# != 2 )); then
  printf '%s\n' 'usage: postprocess.sh raw-report.csv partner.csv' >&2
  exit 2
fi
LC_ALL=C awk '
function fail() { bad = 1; print "invalid BTEQ report row " NR > "/dev/stderr"; exit 1 }
function cents(value, parts, negative) {
  if (value !~ /^-?[0-9]*\.[0-9][0-9]$/) fail()
  negative = sub(/^-/, "", value)
  split(value, parts, ".")
  return (negative ? -1 : 1) * (parts[1] * 100 + parts[2])
}
BEGIN {
  FS = ","
  OFS = ","
  print "invoice_no,account_no,invoice_date,amount_due,tax_amt,open_balance,currency"
}
/^[[:space:]]*$/ { next }
{
  if (NF != 7) fail()
  for (i = 1; i <= NF; i++) {
    sub(/^[[:space:]]+/, "", $i)
    sub(/[[:space:]]+$/, "", $i)
  }
  if ($1 !~ /^INV-[A-Za-z0-9-]+$/ || $2 !~ /^(A[0-9]+|ACC-[0-9]+)$/ ||
      $3 !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/ ||
      $7 !~ /^[A-Z][A-Z][A-Z]$/) fail()
  if (seen[$1]++) fail()
  for (i = 4; i <= 6; i++) {
    amount = cents($i)
    if (amount > 9000000000000 || amount < -9000000000000) fail()
    if (i == 4) total += amount
    absolute = amount < 0 ? -amount : amount
    $i = sprintf("%s%.0f.%02d", amount < 0 ? "-" : "", int(absolute / 100), absolute % 100)
  }
  if (total > 9000000000000 || total < -9000000000000) fail()
  print $1, $2, $3, $4, $5, $6, $7
  count++
}
END {
  if (!bad) {
    absolute = total < 0 ? -total : total
    printf "TRAILER,%d,%s%.0f.%02d\n", count, total < 0 ? "-" : "", int(absolute / 100), absolute % 100
  }
}' "$1" > "$2"
