#!/usr/bin/env bash
set -euo pipefail
minor=${1:-1.34}
case "$minor" in
  1.34|1.35) ;;
  *) printf 'Usage: %s [1.34|1.35]\n' "$0" >&2; exit 2 ;;
esac
kind delete cluster --name "devops-20261128-${minor//./-}"
