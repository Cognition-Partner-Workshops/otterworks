#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/fixtures.sh"

if [[ $# == 0 ]]; then
  set -- "${WORKLOADS[@]}"
fi
for workload in "$@"; do
  render_or_install template "$workload"
  printf '\n---\n'
done
