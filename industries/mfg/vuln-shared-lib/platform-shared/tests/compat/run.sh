#!/usr/bin/env bash
set -euo pipefail
library="$(cd "$(dirname "$0")/../.." && pwd)"
repo="$(git -C "$library" rev-parse --show-toplevel)"
work="$library/artifacts/compat"
mkdir -p "$work/seed" "$work/feed" "$work/consumer"
git -C "$repo" archive ad7b313dc36473216897731f88971eea7c9c96b1 industries/mfg/vuln-shared-lib/platform-shared | tar -x -C "$work/seed"
dotnet pack "$work/seed/industries/mfg/vuln-shared-lib/platform-shared/src/Platform.Shared/Platform.Shared.csproj" -c Release -o "$work/feed"
cp "$library/tests/compat/Consumer.csproj" "$library/tests/compat/Program.cs" "$work/consumer/"
dotnet restore "$work/consumer/Consumer.csproj" --source "$work/feed" --packages "$work/packages" --force
dotnet build "$work/consumer/Consumer.csproj" --no-restore -c Release
dotnet build "$library/src/Platform.Shared/Platform.Shared.csproj" -c Release
cp "$work/seed/industries/mfg/vuln-shared-lib/platform-shared/src/Platform.Shared/bin/Release/net8.0/Platform.Shared.dll" "$work/consumer/bin/Release/net8.0/Platform.Shared.dll"
dotnet "$work/consumer/bin/Release/net8.0/Consumer.dll"
cp "$library/src/Platform.Shared/bin/Release/net8.0/Platform.Shared.dll" "$work/consumer/bin/Release/net8.0/Platform.Shared.dll"
unset PLATFORM_SHARED_FETCH_ALLOWED_HOSTS PLATFORM_SHARED_SIGNING_KEY
dotnet "$work/consumer/bin/Release/net8.0/Consumer.dll"
