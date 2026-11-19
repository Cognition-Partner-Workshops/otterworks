# iOS user-flow harness

From `frontend/client-app` on a Mac with Xcode and an iOS simulator installed:

```sh
bash mobile/ios/scripts/run-ui-tests.sh
# Optional destination and xcodebuild arguments:
IOS_DESTINATION='platform=iOS Simulator,name=iPhone 17' bash mobile/ios/scripts/run-ui-tests.sh -only-testing:AppUITests/AppUITests/testSearch
```

The runner installs npm dependencies, owns a mock on localhost port 8080, builds
web assets with empty API/collaboration overrides to exercise the defaults, syncs Capacitor and runs
the shared App scheme. It stops the mock even if tests fail. Do not run the
browser and native suites simultaneously: both reset the same in-memory state.
Generated public assets and Capacitor config are intentionally not committed.

Browser counterpart (no Xcode required):

```sh
npm ci
npx playwright install webkit
npm run test:e2e:iphone
```

This project starts its own mock and Vite on port 3001. Web requests use Vite's
API_GATEWAY_URL proxy because the web API client intentionally ignores the native
VITE_API_BASE_URL override. The npm script sets `PW_IOS_FLOWS=1`, which enables
the `webkit-iphone` project and its mock/Vite servers. Without this switch the
configuration exposes only Chromium and the original web server; existing
Chromium tests and CI commands stay separate.

## Adding a flow

* Extend `AppUITestCase` in `App/AppUITests/AppUITests.swift`; use `login()`,
  `navigate()` and `assertText()`. Setup resets the backend and signs out a previous
  WKWebView session through the UI. Keep test parallelisation off.
* Use `element()` for WKWebView label queries, `reveal()` to scroll a control
  into view and `fill()` to clear/type after keyboard focus. Card-title flows
  double-tap the visible text rather than the outer card's composite link label.
  Document-save verification polls the backend instead of racing the HTTP save.
* Add browser flows under `e2e/ios-flows/`. The fixture reset runs before each
  test; this suite is serial because the server state is shared.
* Run the server contract test with `npm run test:mock-api`.
* Add realistic response shapes and fixtures to `mock-api/server.mjs`, matching
  `src/lib/api.ts`. Unknown routes return 404, never a catch-all success.
* Credentials: `tester@example.com` / `HarborPass123!`. POST `/__reset` restores
  fixtures. GET `/health` is the readiness probe. The server is local-only and
  accepts any nonempty Authorization header; it is not a production auth service.

Collaboration deliberately returns WebSocket 503 (offline mode): editor tests
verify HTTP save persistence, not multi-user Yjs synchronisation. Native upload
currently asserts the picker entry point, as the simulator has no seeded Files
provider; the WebKit counterpart exercises a real multipart upload. Native
download only tests the button: the known blob-anchor/Filesystem persistence bug
is not fixed by this harness. Browser tests assert the download event. The native
API default is exercised by `testDefaultLocalBackendLogin`, which signs in and
loads a backend file fixture.
Do not fix application bugs in harness changes. Only add a named skip/expected
failure for a confirmed application bug, not a query or interaction failure.

The portrait header/close buttons currently overlap the iOS status bar (known
safe-area bug). Native navigation briefly rotates to landscape to operate the
sidebar controls, waits for viewport layout, then returns to portrait. Login
starts in portrait, dismisses the keyboard before submitting and normalises the
viewport after input auto-zoom. `testPortraitMenuReopens` records the header regression as an
expected failure; `testDownloadPersistsToFiles` is explicitly skipped until the
Filesystem download fix lands. Navigation-only assertions can leave the sidebar
open with `navigate("Files", dismissSidebar: false)`.

The shared SwiftPM `Package.resolved` pins the Capacitor revision for reproducible
Xcode test builds; keep it in version control, unlike built web assets and reports.

## Network configuration

Native development defaults are `http://localhost:8080/api/v1` and
`ws://localhost:8085` on iOS Simulator, and `http://10.0.2.2:8080/api/v1`
and `ws://10.0.2.2:8085` on Android Emulator. Web keeps the same-origin
`/api/v1` proxy and uses `ws://localhost:8085` (or `wss` on HTTPS pages).

For physical devices and production builds, set `VITE_API_BASE_URL` to an
accessible HTTPS API URL (including `/api/v1`) and `VITE_COLLAB_WS_URL` to
an accessible WSS endpoint **before** `npm run build && npx cap sync ios`.
Nonempty overrides win on native; the web API still uses its same-origin proxy.
Simulator localhost refers to the Mac; physical-device localhost does not.

Only Debug enables ATS `NSAllowsLocalNetworking`, via Info.plist preprocessing
and `debug.xcconfig`. Release omits the ATS dictionary and keeps default ATS;
no arbitrary-load exception is enabled. The UI runner always uses Debug and
empty build-time overrides (also masking any local .env URL values).

## Current native validation status

The iPhone 17 / iOS 26.5 full run executes 12 tests with 1 skipped and 0 failures:
10 ordinary passes, the documented safe-area expected failure and the Filesystem
download skip above. All six previously failing flows pass without additional
skips or expected failures. The mocked WebKit suite passes all 7 flows; it does
not substitute for native validation. XCTest failures retain a screenshot and
accessibility hierarchy in the result bundle for follow-up. Margins data can be
below the fold and the wide table can scale the viewport; use `reveal()` instead
of assuming table cells start on-screen or that CSS content fills the screen.
