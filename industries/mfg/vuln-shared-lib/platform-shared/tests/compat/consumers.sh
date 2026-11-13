#!/usr/bin/env bash
set -euo pipefail
library="$(cd "$(dirname "$0")/../.." && pwd)"
estate="$(dirname "$library")"
work="$library/artifacts/consumer-compat"
mkdir -p "$work"
make -C "$estate/dev-api" test
make -C "$estate/dealer-portal" bff-test
mapfile -d '' assemblies < <(find "$estate/dev-api/tests" "$estate/dealer-portal/bff/tests" -path '*/bin/Release/net8.0/Platform.Shared.dll' -print0)
restore() {
    for i in "${!assemblies[@]}"; do
        if [[ -f "$work/$i.dll" ]]; then cp "$work/$i.dll" "${assemblies[$i]}"; fi
    done
}
trap restore EXIT
for i in "${!assemblies[@]}"; do
    cp "${assemblies[$i]}" "$work/$i.dll"
    cp "$library/src/Platform.Shared/bin/Release/net8.0/Platform.Shared.dll" "${assemblies[$i]}"
done
echo "Consumer suites compiled against their pinned package, executing with the new Platform.Shared DLL:"
dotnet test "$estate/dev-api/DevApi.sln" --no-build --no-restore -c Release
dotnet test "$estate/dealer-portal/bff/DealerPortal.Bff.sln" --no-build --no-restore -c Release
