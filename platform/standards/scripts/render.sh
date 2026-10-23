#!/usr/bin/env bash
# Render an application's chart the way the pipeline does.
#   render.sh <app-dir> <image-repository> <image-tag> [extra helm args]
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
app_dir="$1"; repo="$2"; tag="$3"; shift 3
values=(-f "$app_dir/deploy/values.yaml")
[[ -f "$app_dir/deploy/values-ci.yaml" ]] && values+=(-f "$app_dir/deploy/values-ci.yaml")
helm template "$(basename "$app_dir")" "$here/helm/app" "${values[@]}" \
  --set image.repository="$repo" --set image.tag="$tag" "$@"
