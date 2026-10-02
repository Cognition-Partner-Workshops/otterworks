#!/usr/bin/env bash
# Assume a cloud-worker Devin role and print export lines for it.
#   source <(cloudworker/assume.sh observer devin-<session id>)
#   source <(cloudworker/assume.sh builder devin-<session id> --kubeconfig)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
READER_FILE="${HERE}/.state/devin-cw-reader.json"
AWS_REGION="${AWS_REGION:-us-east-1}"
EKS_CLUSTER="${EKS_CLUSTER:-otterworks-dev}"

die() { echo "assume.sh: $*" >&2; exit 1; }

ROLE=""; SESSION=""; KUBECONFIG_UPDATE=false
for arg in "$@"; do
  case "$arg" in
    --kubeconfig) KUBECONFIG_UPDATE=true ;;
    -h|--help) sed -n '2,4p' "$0" >&2; exit 0 ;;
    *) if [ -z "$ROLE" ]; then ROLE="$arg"; elif [ -z "$SESSION" ]; then SESSION="$arg"; else die "unexpected argument: $arg"; fi ;;
  esac
done
SESSION="${SESSION:-devin-manual}"

if [ -f "$READER_FILE" ]; then
  : "${CW_AWS_ACCESS_KEY_ID:=$(jq -r '.CW_AWS_ACCESS_KEY_ID // empty' "$READER_FILE")}"
  : "${CW_AWS_SECRET_ACCESS_KEY:=$(jq -r '.CW_AWS_SECRET_ACCESS_KEY // empty' "$READER_FILE")}"
  : "${CW_OBSERVER_ROLE_ARN:=$(jq -r '.CW_OBSERVER_ROLE_ARN // empty' "$READER_FILE")}"
  : "${CW_BUILDER_ROLE_ARN:=$(jq -r '.CW_BUILDER_ROLE_ARN // empty' "$READER_FILE")}"
fi

case "$ROLE" in
  observer) ROLE_ARN="${CW_OBSERVER_ROLE_ARN:-}" ;;
  builder)  ROLE_ARN="${CW_BUILDER_ROLE_ARN:-}" ;;
  *) die "usage: assume.sh observer|builder [session-name] [--kubeconfig]" ;;
esac
[ -n "${CW_AWS_ACCESS_KEY_ID:-}" ] || die "CW_AWS_ACCESS_KEY_ID is not set"
[ -n "${CW_AWS_SECRET_ACCESS_KEY:-}" ] || die "CW_AWS_SECRET_ACCESS_KEY is not set"
[ -n "$ROLE_ARN" ] || die "CW_$(echo "$ROLE" | tr '[:lower:]' '[:upper:]')_ROLE_ARN is not set"
[[ "$SESSION" =~ ^[A-Za-z0-9+=,.@_-]{2,64}$ ]] || die "invalid session name: $SESSION"

creds="$(env -u AWS_PROFILE -u AWS_SESSION_TOKEN \
  AWS_ACCESS_KEY_ID="$CW_AWS_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$CW_AWS_SECRET_ACCESS_KEY" \
  aws sts assume-role --region "$AWS_REGION" --role-arn "$ROLE_ARN" --role-session-name "$SESSION" \
  --duration-seconds "${CW_SESSION_SECONDS:-3600}" --query Credentials --output json)"

key_id="$(jq -r .AccessKeyId <<<"$creds")"
secret="$(jq -r .SecretAccessKey <<<"$creds")"
token="$(jq -r .SessionToken <<<"$creds")"

if [ "$KUBECONFIG_UPDATE" = true ]; then
  env -u AWS_PROFILE AWS_ACCESS_KEY_ID="$key_id" AWS_SECRET_ACCESS_KEY="$secret" AWS_SESSION_TOKEN="$token" \
    aws eks update-kubeconfig --name "$EKS_CLUSTER" --region "$AWS_REGION" >&2
fi

printf 'export AWS_ACCESS_KEY_ID=%q\n' "$key_id"
printf 'export AWS_SECRET_ACCESS_KEY=%q\n' "$secret"
printf 'export AWS_SESSION_TOKEN=%q\n' "$token"
echo "assume.sh: ${ROLE} as session ${SESSION} until $(jq -r .Expiration <<<"$creds")" >&2
