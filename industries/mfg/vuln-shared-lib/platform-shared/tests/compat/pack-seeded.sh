#!/usr/bin/env bash
set -euo pipefail
library="$(cd "$(dirname "$0")/../.." && pwd)"
repo="$(git -C "$library" rev-parse --show-toplevel)"
work="$library/artifacts/seeded"
feed="${1:-$library/artifacts/feed}"
seed="${VSL_SEEDED_REF:-seeded-v1}"
if ! git -C "$repo" cat-file -e "$seed^{commit}" 2>/dev/null; then
    seed=ad7b313dc36473216897731f88971eea7c9c96b1
    if ! git -C "$repo" cat-file -e "$seed^{commit}" 2>/dev/null; then
        git -C "$repo" fetch origin tag seeded-v1
        seed=seeded-v1
    fi
fi
mkdir -p "$work" "$feed"
git -C "$repo" archive "$seed" industries/mfg/vuln-shared-lib/platform-shared | tar -x -C "$work"
dotnet pack "$work/industries/mfg/vuln-shared-lib/platform-shared/src/Platform.Shared/Platform.Shared.csproj" -c Release -o "$feed"
