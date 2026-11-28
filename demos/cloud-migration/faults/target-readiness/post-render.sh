#!/usr/bin/env bash
set -euo pipefail

config_dir="$(dirname -- "${BASH_SOURCE[0]}")"
workdir="$(mktemp -d)"
trap 'rm -rf -- "$workdir"' EXIT
cp -- "$config_dir/kustomization.yaml" "$workdir/"
cat > "$workdir/rendered.yaml"
kubectl kustomize "$workdir"
