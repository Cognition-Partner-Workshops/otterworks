#!/usr/bin/env bash
set -euo pipefail
if (( $# != 1 )) || [[ ! -f $1 ]]; then
  printf '%s\n' 'usage: sftp_push.sh existing.csv' >&2
  exit 2
fi
if [[ ${SFTP_DRY_RUN:-1} != 1 ]]; then
  printf '%s\n' 'SFTP live transfer is not implemented; set SFTP_DRY_RUN=1' >&2
  exit 1
fi
file=$1
key=${SFTP_KEY_PATH:-/fake/keys/partner_sftp}
remote=${SFTP_REMOTE_DIR:-/incoming}/$(basename -- "$file")
for value in "$file" "$key" "$remote"; do
  if [[ $value == *[\"\\$'\n'$'\r']* ]]; then
    printf '%s\n' 'SFTP paths cannot contain quotes, backslashes or newlines' >&2
    exit 2
  fi
done
printf "sftp -i %q -b - partner@sftp.partner.example <<'SFTP_BATCH'\n" "$key"
printf 'put "%s" "%s"\n' "$file" "$remote"
printf '%s\n' 'bye' 'SFTP_BATCH'
