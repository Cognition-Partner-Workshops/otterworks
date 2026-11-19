#!/usr/bin/env bash
set -euo pipefail
input=$(cat)
printf '%s\n' "$input" > "${BTEQ_CAPTURE:?}"
if [[ ${FAKE_BTEQ_FAIL:-0} == 1 ]]; then
  exit 8
fi
export_file=$(printf '%s\n' "$input" | sed -n 's/^\.EXPORT REPORT FILE="\(.*\)"$/\1/p')
[[ -n $export_file ]]
cp -- "${RAW_FIXTURE:?}" "$export_file"
