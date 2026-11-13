#!/usr/bin/env bash
set -euo pipefail
library="$(cd "$(dirname "$0")/../.." && pwd)"
repo="$(git -C "$library" rev-parse --show-toplevel)"
work="$library/artifacts/seeded"
feed="${1:-$library/artifacts/feed}"
if ! git -C "$repo" rev-parse --verify seeded-v1 >/dev/null 2>&1; then
    git -C "$repo" fetch origin tag seeded-v1
fi
mkdir -p "$work" "$feed"
git -C "$repo" archive seeded-v1 industries/mfg/vuln-shared-lib/platform-shared | tar -x -C "$work"
dotnet pack "$work/industries/mfg/vuln-shared-lib/platform-shared/src/Platform.Shared/Platform.Shared.csproj" -c Release -o "$feed"
