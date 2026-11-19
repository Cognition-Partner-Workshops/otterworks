#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/../template/submit.sh" user_pref_json_flatten
