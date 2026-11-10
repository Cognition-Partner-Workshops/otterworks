#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$@" > "${EXPORT_CAPTURE:?}"
if [[ ${FAKE_EXPORT_FAIL:-0} == 1 ]]; then
  exit 8
fi
[[ $# == 2 ]]
cp -- "${RAW_FIXTURE:?}" "$2"
