#!/usr/bin/env bash
set -euo pipefail
set +x

if [[ $# -ne 2 ]]; then
  printf 'Usage: %s <webhook-url> <fixture>\n' "$0" >&2
  exit 2
fi
[[ "$1" == https://* ]] || { printf 'Webhook must use HTTPS.\n' >&2; exit 2; }
: "${DEVIN_WEBHOOK_BEARER:?Set the bearer secret in DEVIN_WEBHOOK_BEARER}"
[[ "$DEVIN_WEBHOOK_BEARER" =~ ^[A-Za-z0-9_.~+/=-]+$ ]] || {
  printf 'Bearer token contains unsupported characters.\n' >&2; exit 2;
}
key=$(python3 -c 'import hashlib,json,sys; data=json.load(open(sys.argv[1], encoding="utf-8")); print(hashlib.sha256((data["alarm"] + "|" + data["time"]).encode()).hexdigest())' "$2")
printf 'header = "Authorization: Bearer %s"\n' "$DEVIN_WEBHOOK_BEARER" |
  curl --disable --config - --proto '=https' --silent --show-error --fail --max-time 20 \
    -H 'Content-Type: application/json' -H "Idempotency-Key: $key" --data-binary "@$2" -- "$1"
