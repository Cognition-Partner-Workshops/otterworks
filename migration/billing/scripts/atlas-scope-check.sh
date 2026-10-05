#!/usr/bin/env bash
# Usage: migration/billing/scripts/atlas-scope-check.sh --db ow_tp_billing_<run> [--out <path>]
#
# Proves the principal in MONGODB_ATLAS_URI holds readWrite on the migration database only.
# The URI is read from the environment by name; it is never accepted on the command line and
# never printed. Fails closed (exit 2, verdict FAIL) when the variable is unset or empty, when
# --db is missing, or when an argument looks like a connection string.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
URI_ENV="MONGODB_ATLAS_URI"
DB=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[$i]}" in
    mongodb://*|mongodb+srv://*|*://*@*)
      echo "atlas_scope_check: FAIL - a connection string was passed as an argument; set $URI_ENV instead" >&2
      exit 2 ;;
    --uri-env|--uri-env=*)
      echo "atlas_scope_check: FAIL - the principal is always read from $URI_ENV; --uri-env is not accepted" >&2
      exit 2 ;;
    --db) DB="${args[$((i + 1))]:-}" ;;
    --db=*) DB="${args[$i]#--db=}" ;;
  esac
done
if [ -z "$DB" ]; then
  echo "atlas_scope_check: FAIL - --db ow_tp_billing_<run> is required" >&2
  exit 2
fi
if [ -z "${MONGODB_ATLAS_URI:-}" ]; then
  echo "atlas_scope_check: FAIL - $URI_ENV is not set; no connection attempted (db=$DB)" >&2
  exit 2
fi
redact() { sed -E 's#mongodb(\+srv)?://[^[:space:]"]+#mongodb://<redacted>#g'; }
set +e
uv run --no-project --with pymongo==4.10.1 "$HERE/atlas_scope_check.py" --uri-env "$URI_ENV" "$@" 2>&1 | redact
rc=${PIPESTATUS[0]}
set -e
exit "$rc"
