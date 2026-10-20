#!/usr/bin/env bash
# Run the platform policy gate on an application directory: Dockerfile rules,
# then the rendered chart. Exit code is non-zero when any rule is broken.
#   policy-check.sh <app-dir> <image-repository> <image-tag> [extra helm args]
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
app_dir="$1"; repo="$2"; tag="$3"; shift 3
status=0
echo "== Dockerfile policy ($app_dir/Dockerfile)"
conftest test --no-color --parser dockerfile --policy "$here/policy/conftest" \
  --data "$here/base-images.yaml" --namespace platform.dockerfile "$app_dir/Dockerfile" || status=1
echo "== Manifest policy (helm template)"
"$here/scripts/render.sh" "$app_dir" "$repo" "$tag" "$@" > /tmp/platform-rendered.yaml
conftest test --no-color --policy "$here/policy/conftest" --data "$here/policy/conftest/data" \
  --namespace platform.k8s /tmp/platform-rendered.yaml || status=1
exit $status
