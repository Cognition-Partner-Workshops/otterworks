#!/usr/bin/env bash
# run.sh <POLICIES> <OUT>  - run the RATEPREM batch against the flat-file tables
# Last stdout line: RATEPREM READ=<n> OK=<n> DEC=<n> REJ=<n>
# Exit: 0 ok | 12 I/O error. RATEPREM_TABLES overrides the table directory.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POL="$(realpath "${1:?usage: run.sh <POLICIES> <OUT>}")"
OUT="${2:?usage: run.sh <POLICIES> <OUT>}"
mkdir -p "$(dirname "$OUT")"
RATEPREM_POLICIES="$POL" RATEPREM_OUT="$(realpath -m "$OUT")" \
RATEPREM_TABLES="${RATEPREM_TABLES:-$HERE/../tables}" \
  "$HERE/bin/RATEPREM"
