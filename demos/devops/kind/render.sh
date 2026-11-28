#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/fixtures.sh"

flags=()
if [[ ${1:-} == --deployments ]]; then
  flags=(--show-only templates/deployment.yaml)
  shift
fi
if [[ $# == 0 ]]; then
  set -- "${WORKLOADS[@]}"
fi
for workload in "$@"; do
  render_or_install template "$workload" "${flags[@]}"
  printf '\n---\n'
done
