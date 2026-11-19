#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
if curl -fsS http://127.0.0.1:4010/health >/dev/null 2>&1; then
  echo 'Port 4010 is already in use; stop the existing mock first.' >&2
  exit 1
fi
node mock-api/server.mjs &
mock_pid=$!
trap 'kill "$mock_pid" 2>/dev/null || true' EXIT
for _ in {1..50}; do
  if curl -fsS http://127.0.0.1:4010/health >/dev/null 2>&1; then break; fi
  sleep 0.1
done
curl -fsS http://127.0.0.1:4010/health >/dev/null
npm ci
VITE_STORAGE_PUBLIC_URL=http://127.0.0.1:4010 VITE_API_BASE_URL=http://127.0.0.1:4010/api/v1 VITE_COLLAB_WS_URL=ws://127.0.0.1:4010 npm run build
npx cap sync ios
xcodebuild test -project mobile/ios/App/App.xcodeproj -scheme App \
  -destination "${IOS_DESTINATION:-platform=iOS Simulator,id=EDD9B083-63F1-44E6-9A7B-0A6964CC2561}" \
  -parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO "$@"
