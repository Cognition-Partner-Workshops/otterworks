#!/usr/bin/env bash
set -euo pipefail
usage() { echo 'Usage: scenario.sh arm|disarm|status|reset odl-read-latency [duration-seconds (arm only)]' >&2; exit 2; }
[[ $# -ge 2 && $# -le 3 && "$2" == odl-read-latency ]] || usage
case "$1" in
  arm) [[ $# -eq 2 || "$3" =~ ^[0-9]+$ ]] || usage ;;
  disarm|status|reset) [[ $# -eq 2 ]] || usage ;;
  *) usage ;;
esac
HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${HERE}/scenario.py" "$@"
