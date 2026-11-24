#!/usr/bin/env bash
# run.sh quote <POLICIES> <OUT>   quote every policy headlessly
# run.sh build                    load the package into a working image
# run.sh screen [PORT]             serve the online quote screen (default 8091)
# PHARO (vm) and PHARO_IMAGE locate Pharo; RATEPREM_TABLES overrides the tables.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHARO="${PHARO:-pharo}"
WORK="${PHARO_WORK:-$HERE/build}"
TABLES="$(realpath "${RATEPREM_TABLES:-$HERE/../tables}")"
mkdir -p "$WORK"
if [ ! -f "$WORK/InsRating.image" ]; then
  cp "${PHARO_IMAGE:?set PHARO_IMAGE to a Pharo 12 image}" "$WORK/InsRating.image"
  cp "${PHARO_IMAGE%.image}.changes" "$WORK/InsRating.changes"
  cp "$(dirname "$PHARO_IMAGE")"/*.sources "$WORK/" 2>/dev/null || true
  INSRATING_SRC="$HERE/src" "$PHARO" --headless "$WORK/InsRating.image" st --save --quit "$HERE/load.st"
fi
case "${1:-}" in
  quote)
    POL="$(realpath "${2:?policies}")"; OUT="$(realpath -m "${3:?out}")"
    "$PHARO" --headless "$WORK/InsRating.image" eval \
      "InsQuoteBatch runPolicies: '$POL' tables: '$TABLES' out: '$OUT'" | tr -d "'" ;;
  screen)
    "$PHARO" --headless "$WORK/InsRating.image" eval --no-quit \
      "InsQuoteScreen serveOn: ${2:-8091} tables: '$TABLES'. 'quote screen up'" ;;
  build) echo "image ready: $WORK/InsRating.image" ;;
  *) echo "usage: run.sh build | quote <POLICIES> <OUT> | screen [PORT]" >&2; exit 2 ;;
esac
