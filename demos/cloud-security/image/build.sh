#!/usr/bin/env bash
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
service="$root/services/document-service"
fixture="${2:-$root/demos/cloud-security/image}"
base="$(python3 - "$root/platform/standards/base-images.yaml" <<'PY'
import sys
import yaml

with open(sys.argv[1]) as source:
    images = yaml.safe_load(source)["base_images"]
print(next(entry["image"] for entry in images if entry["name"] == "python-3.12-slim"))
PY
)"
if [[ $(awk '/^FROM python:3\.12-slim( |$)/ {n++} END {print n+0}' "$service/Dockerfile") != 2 || $base != *@sha256:* ]]; then
    echo 'The document-service base no longer matches the approved fixture input.' >&2
    exit 2
fi

{
    sed "s#^FROM python:3\.12-slim\( \|$\)#FROM $base\1#" "$service/Dockerfile"
    printf '%s\n' 'USER root' \
        'RUN --mount=type=bind,from=fixture,source=requirements.lock,target=/tmp/requirements.lock python -m pip install --no-cache-dir --no-deps --require-hashes --target /opt/control-fixture -r /tmp/requirements.lock' \
        'USER appuser'
} | docker buildx build --load --build-context "fixture=$fixture" -f - -t "${1:?supply a local image tag}" "$service"
