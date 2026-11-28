#!/usr/bin/env bash
set -euo pipefail

root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
source "$root/demos/cloud-security/image/scanner.lock"
image="${1:?supply a local image tag}"
cache="${2:?supply a local scanner cache directory}"

if [[ $(trivy --version | head -n1) != "Version: $TRIVY_VERSION" ]]; then
    echo "Expected Trivy $TRIVY_VERSION." >&2
    exit 2
fi

prepare_db() {
    trivy --cache-dir "$cache" image --download-db-only --db-repository "$TRIVY_DB_IMAGE"
    printf '%s\n' "$TRIVY_DB_IMAGE" > "$cache/fixture-db.ref"
    (cd "$cache" && sha256sum db/trivy.db db/metadata.json > fixture-db.sha256)
}

if [[ ! -f "$cache/fixture-db.ref" ]]; then
    if [[ -e "$cache/db/trivy.db" ]]; then
        echo 'Use a fresh cache for the pinned fixture database.' >&2
        exit 2
    fi
    prepare_db
fi
[[ $(<"$cache/fixture-db.ref") == "$TRIVY_DB_IMAGE" ]]
(cd "$cache" && sha256sum --check --status fixture-db.sha256)

cd "$root"
trivy --config security/scanning/trivy-config.yaml --cache-dir "$cache" image \
    --image-src docker --scanners vuln --skip-db-update --skip-java-db-update --offline-scan \
    --format json --output "${3:?supply a scan JSON destination}" "$image"
