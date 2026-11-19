# Angular admin → React port inventory

Static inventory of the Angular source alongside the React port at `frontend/client-app/src/admin/`. No servers, API requests, fixture resets, or browser sessions were used to prepare this document.

## Counting and scope

- Paths below are relative to `frontend/admin-dashboard/`, unless explicitly stated otherwise. Page component paths are relative to `src/app/pages/`; shared paths are relative to `src/app/`.
- **Angular lines = total / template / spec**: physical lines, including comments and blanks. Total is the component `.ts` file (inline template and styles included); template is its inclusive opening-to-closing backtick line span; spec is the adjacent `.component.spec.ts`, or `0` if absent. Template lines are a subset of total, not an additional file. Archive-compare is counted separately from its parent.
- Material names in the pages table abbreviate `Mat{Name}Module` (for example, `ProgressSpinner` means `MatProgressSpinnerModule`). These are the modules declared in the standalone component's `imports`, not a count of rendered widgets. Chart.js / `ng2-charts` are additional non-Material dependencies.
- **Size buckets describe relative porting complexity, not time estimates**: S = simple form/list; M = table, filters, or modest mutations; L = multiple charts, rich detail, or report workflows; XL = coordinated state, side effects, or cross-deployment comparison. They are deliberately not line-count thresholds.
- **Ported** means a working React implementation, not pixel parity. Angular `/login`, `/`, and `/users` correspond to React `/admin/login`, `/admin`, and `/admin/users`. Everything else remains Angular; the React user-detail placeholder and legacy links do **not** count as ports. Routes are sourced from `src/app/app.routes.ts` (68 lines).
- Endpoint paths below are resolved from the services, not inferred from method names or older model comments. `{id}`, `{runId}`, and `{docId}` denote runtime values; migration IDs are URL-encoded.

## 1. Pages

| Page / Angular route | Component file | Angular lines: total / template / spec | Material modules | HTTP calls made by this page | Notable complexity / behavior to preserve | Size | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Login — `/login` | `login/login.component.ts` | 167 / 40 / 55 | Card, Input, Button, Icon, ProgressSpinner, FormField | Via AuthService: `POST /api/v1/auth/login` | Template-driven form, required email/password, password visibility, loading; any gateway error falls back to an 800 ms mock login accepting a nonempty password. Shared admin storage keys. | S | Ported |
| Dashboard — `/` | `dashboard/dashboard.component.ts` | 230 / 91 / 57 | Card, Icon, ProgressSpinner | `GET /api/v1/admin/metrics/summary` twice initially: stats and analytics | Four cards; two Chart.js charts; role counts labelled “User Signups”; independent stats/chart requests; stats-only refresh subscription; infinite initial spinner on error. Growth/documents hardcoded zero by mapper. | M | Ported |
| Users — `/users` | `users/users.component.ts` | 271 / 106 / 63 | Table, Paginator, Sort, Input, FormField, Button, Icon, Chips, Menu, Select, ProgressSpinner, SnackBar, Dialog | `GET /api/v1/admin/users`;<br>`PUT /api/v1/admin/users/{id}/suspend`;<br>`PUT /api/v1/admin/users/{id}/activate`;<br>`DELETE /api/v1/admin/users/{id}` | Client-side table/filter/sort/pagination; 5-row default; name/email-only search; role/status AND filters; status-dependent menus; suspend/delete dialogs, immediate restore, snackbars; mutation reload resets pagination/sort but retains filters; initial error leaves spinner. | M | Ported |
| User detail — `/users/:id` | `user-detail/user-detail.component.ts` | 297 / 125 / 0 | Card, Icon, Button, ProgressSpinner, ProgressBar, Table, Chips, SnackBar, Dialog | `GET /api/v1/admin/users/{id}`;<br>`GET /api/v1/admin/audit-logs?actor_id={id}&per_page=20`;<br>`PUT /api/v1/admin/users/{id}/suspend`;<br>`PUT /api/v1/admin/users/{id}/activate`;<br>`DELETE /api/v1/admin/users/{id}` | Parallel profile/activity subscriptions; storage usage and activity table; suspend/delete confirmation and restore; navigation after deletion. React currently only preserves the detail URL and offers an Angular link. | L | Not ported |
| Audit — `/audit` | `audit/audit.component.ts` | 216 / 93 / 0 | Table, Paginator, Sort, Input, FormField, Select, Icon, Chips, ProgressSpinner, Button | `GET /api/v1/admin/audit-logs` | Client-side table/paginator/sort; text matches actor/action/resource/details, ANDed with action/severity selectors; action normalization and severity derivation in service. | M | Not ported |
| Features — `/features` | `features/features.component.ts` | 143 / 48 / 0 | Card, Icon, SlideToggle, ProgressSpinner, Chips, Input, FormField, SnackBar | `GET /api/v1/admin/features`;<br>`PUT /api/v1/admin/features/{id}` with `{ feature: { enabled } }` | Search name/description/key; slide-toggle state and success snackbar. Handler does not reload the list or assign the returned model; do not silently change its state semantics during a faithful port. | S | Not ported |
| Health — `/health` | `health/health.component.ts` | 203 / 80 / 56 | Card, Icon, Button, ProgressSpinner, Chips | `GET /api/v1/admin/health/services` | Manual refresh, loading/error states and health counts; service mapper adds metadata and database/Redis pseudo-services. No timed polling in this component. | M | Not ported |
| Announcements — `/announcements` | `announcements/announcements.component.ts` | 233 / 99 / 0 | Card, Icon, Button, ProgressSpinner, Chips, Input, FormField, Select, SnackBar, Dialog | `GET /api/v1/admin/announcements`;<br>`POST /api/v1/admin/announcements`;<br>`PUT /api/v1/admin/announcements/{id}` (publish);<br>`DELETE /api/v1/admin/announcements/{id}` | Template-driven creation form; title/body, priority/audience conversion, draft/published state; delete confirmation; snackbars and reload after mutations. | M | Not ported |
| Storage quotas — `/quotas` | `quotas/quotas.component.ts` | 180 / 81 / 0 | Table, Paginator, Sort, Input, FormField, Button, Icon, ProgressSpinner, ProgressBar, Select, SnackBar | `GET /api/v1/admin/users`;<br>`PUT /api/v1/admin/quotas/{id}` with `{ quota: { quota_bytes } }` | Table/search/paginator/sort; byte formatting, percentage/progress bars, per-row quota selection. Update handler shows snackbar without reloading/assigning the response. | M | Not ported |
| Analytics — `/analytics` | `analytics/analytics.component.ts` | 205 / 81 / 0 | Card, Icon, ProgressSpinner, Button | `GET /api/v1/admin/metrics/summary` | Five Chart.js charts (two line, one pie, two bar); labels imply time series although mapper supplies role/status/tier aggregates; file types and peak hours are empty arrays. Preserve/finalize these semantics explicitly, not accidentally. | L | Not ported |
| Incidents — `/incidents` | `incidents/incidents.component.ts` | 710 / 327 / 193 | Card, Icon, Button, ProgressSpinner, Chips, Input, FormField, Select, SnackBar, Badge, Tooltip, SlideToggle, Dialog | `GET /api/v1/admin/incidents`;<br>`POST /api/v1/admin/incidents`;<br>`POST /api/v1/admin/incidents/{id}/trigger_session`;<br>`PATCH /api/v1/admin/incidents/{id}` (status);<br>`DELETE /api/v1/admin/incidents/{id}`;<br>`POST /api/v1/admin/chaos`;<br>`DELETE /api/v1/admin/chaos`;<br>`GET /api/v1/admin/settings/auto_investigate`;<br>`PUT /api/v1/admin/settings/auto_investigate` | Create form, active/status/closed filtering and counts; resolve/close/delete confirmations; Devin-session launch/status/links; chaos controls persist local state; auto-investigation toggle and error feedback. 10-second interval reloads **only when an active incident has a Devin session ID**; unsubscribes on destroy. These mutations are operationally significant, not fixture-only UI controls. | XL | Not ported |
| Migration — `/migration`, `/migration/reconciliation/:runId`, `/migration/archive/:docId` | `migration/migration.component.ts` | 410 / 196 / 132 | Card, Icon, Button, Input, FormField, Select, ProgressSpinner, Tooltip | `GET /api/v1/reports/reconciliation`;<br>`GET /api/v1/reports/reconciliation/{runId}` (`latest` default);<br>`GET /api/v1/reports/reconciliation/{runId}.csv`;<br>`GET /api/v1/reports/reconciliation/{runId}.html`;<br>also embeds archive-compare, whose requests are listed next | Route-driven run selection; `switchMap` cancels stale reports; summary/tables/class totals; rule/issue/table filters; namespace/error hints; authenticated Blob downloads and object-URL cleanup; existing Devin session links (not a session-trigger API here). Embeds archive panel; archive route passes docId and auto-loads it. No report polling. | L | Not ported |
| Archive-compare — embedded in Migration; deep link `/migration/archive/:docId` (no independent routed component) | `migration/archive-compare.component.ts` | 348 / 86 / 173 | Card, Icon, Button, Input, FormField, ProgressSpinner, Tooltip | `GET /config/peer.json` (cached);<br>`GET /api/v1/reports/archive/documents/{docId}`;<br>`GET /api/v1/reports/archive/documents/{docId}/hash`;<br>same document/hash GETs under configured peer base, when present | Concurrent document/hash reads per side; version/policy/event matching and highlighting; hash verdict/missing-hash handling; 404 feature-off hints and network/CORS errors. Peer display host comes from `peer_app_url`; requests prefer `peer_proxy_url` (normally `/peer`) and otherwise use the cross-origin host. Peer 401 must not end the local session. | XL | Not ported |

The archive paths above intentionally use `/api/v1/reports/archive/...`: `MigrationApiService.documentUrl()` is authoritative. Some older model/spec fixture text still mentions `/api/v1/archive/...`.

## 2. Shared / core

### Services and page-area ownership

Line ranges are inclusive and refer to the current files. Shared mappers appear in multiple areas; these ranges are dependencies, **not additive estimates**. `AdminApiService` is 454 lines total.

| Area | Source and line ranges | Responsibility / port implications |
| --- | --- | --- |
| Admin API scaffolding | `core/services/admin-api.service.ts:1–38`, closing class at 454 | Imports; health metadata; severity/priority maps; `/api/v1` base; `statsChanged$` Subject; HTTP injection. Metadata/constants also support the areas below. |
| Dashboard | `admin-api.service.ts:42–46`, `385–399`, `427–433` (same directory) | Summary GET, dashboard mapper, binary byte formatter. Already ported into React admin API; shared chart dependency is below. |
| Users / user detail | `admin-api.service.ts:50–82`, `244–272` | List/detail/activity and suspend/activate/delete methods; user and activity mappers. React has list/mutations/user mapper, not a full detail/activity UI. Null last login falls back to created_at. |
| Unused document mutation | `admin-api.service.ts:84–86` | `deleteDocument` → `DELETE /api/v1/admin/documents/{id}`; no page caller found. Do not attribute this endpoint to Dashboard just because of its document card. |
| Audit | `admin-api.service.ts:90–94`, `274–308` | Audit list, raw event mapping, action normalization and severity. User-detail activity has its own mapper. |
| Features | `admin-api.service.ts:98–108`, `310–321` | List/toggle and raw feature mapper. |
| Health | `admin-api.service.ts:112–116`, `338–383` | Services GET, health-state mapping and synthetic database/Redis entries; uses SERVICE_META from scaffolding. |
| Announcements | `admin-api.service.ts:120–149`, `323–336` | List/create/publish/delete, nested payloads and severity/priority/audience conversion. |
| Quotas | `admin-api.service.ts:153–168`; users method `50–54`, mapper `244–260` | Quota PUT constructs a partial/defaulted User from the response; quota page lists users rather than fetching a separate quota collection. |
| Analytics / dashboard charts | `admin-api.service.ts:172–176`, `401–425` | Summary GET and aggregate-to-chart mapping/fallbacks. Dashboard uses this too; React ports its mapper but not the dedicated analytics page. |
| Incidents | `admin-api.service.ts:180–220`, `435–453` | List/single/create/trigger-session/status/delete and incident mapper. `getIncident` at 186–190 is defined but not called by a page. |
| Chaos and settings (Incidents) | `admin-api.service.ts:224–240` | Chaos POST/DELETE; auto-investigate GET/PUT. Preserve intentional operational controls and explicit errors. |
| Authentication | `core/services/auth.service.ts` — 106 lines | `AuthUser` and gateway types; BehaviorSubject state; `ow_admin_token` / `ow_admin_user`; gateway login, broad error-to-mock fallback, logout navigation. Ported; fallback lives here, **not** in mock-data files. |
| Migration reports | `core/services/migration-api.service.ts` — 88 total; `21–41` | List/report URLs and authenticated CSV/HTML Blob GETs; URL-encoded IDs. Not ported. |
| Archive and peer configuration | `migration-api.service.ts:8–19`, `43–87` (same directory) | PEER_REQUEST context token; document/hash GETs; cached config with no-peer fallback; proxy/cross-origin URL construction. Must move together with interceptor exemption and deployment wiring. Not ported. |

### Models, shell, and presentation

| File | Lines | Responsibility / current React dependency |
| --- | ---: | --- |
| `core/models/user.model.ts` | 24 | User and UserActivity; User fields ported to React admin API; activity still needed for detail. |
| `core/models/analytics.model.ts` | 24 | DashboardStats, ChartDataPoint, AnalyticsReport; equivalent React types/mappers exist, including currently unused analytics fields. |
| `core/models/audit.model.ts` | 12 | AuditEvent and action/severity unions; not ported. |
| `core/models/feature-flag.model.ts` | 10 | FeatureFlag; not ported. |
| `core/models/system-health.model.ts` | 11 | ServiceHealth; not ported. |
| `core/models/announcement.model.ts` | 12 | Announcement, priority/status/audience; not ported. |
| `core/models/incident.model.ts` | 31 | Incident and Devin-session/lifecycle fields; not ported. |
| `core/models/migration.model.ts` | 127 | Reconciliation reports/runs/failures/class totals/session links, archive versions/events/policies/hash, peer config; not ported. |
| `core/guards/auth.guard.ts` | 15 | Token-presence gate, redirects to login. React `AuthGuard` is ported. |
| `core/interceptors/jwt.interceptor.ts` | 38 | Adds bearer token to requests; 401 logs out unless PEER_REQUEST. React admin Axios covers current local routes, **not yet** peer-request semantics. |
| `layout/sidebar/sidebar.component.ts` | 180 (template 29; spec 65) | List, Icon, Tooltip modules; ten destinations, collapse output, active links/logo. React Sidebar exists; unported destinations link to Angular via VITE_ADMIN_LEGACY_URL. |
| `layout/toolbar/toolbar.component.ts` | 65 (template 19; no spec) | Toolbar, Icon, Button, Menu modules; username and Logout. React Toolbar exists. |
| `app.component.ts` | 51 (template 14; no spec) | Authenticated layout vs login outlet, sidebar width/content padding. React AdminApp/Shell implement current surface. |
| `shared/components/confirm-dialog.component.ts` | 38 (template 12; no spec) | Dialog and Button modules; injected title/message/confirm text/color; boolean result. React users have a local native dialog, not yet a general replacement for all other pages. |
| `../styles.scss` (that is, `src/styles.scss`) | 126 | Material theme, typography/reset/scrollbars, navy sidebar and amber active-item overrides. React approximates via Tailwind; no full global Material theme port. |
| `app.routes.ts` / `../main.ts` | 68 / 19 | Lazy routes and auth boundary; standalone bootstrap, HTTP interceptor, animations and global Chart.js registration. Replace routing/bootstrap dependencies only when all remaining Angular routes are retired. |

### Mock-data files and stats notifications

All mock files are under `src/app/core/services/mock-data/`:

| File | Lines | Exports |
| --- | ---: | --- |
| `analytics.mock.ts` | 98 | MOCK_DASHBOARD_STATS, MOCK_ANALYTICS_REPORT, mockStorage, formatStorageUsed |
| `announcements.mock.ts` | 39 | MOCK_ANNOUNCEMENTS |
| `audit.mock.ts` | 79 | MOCK_AUDIT_EVENTS |
| `features.mock.ts` | 54 | MOCK_FEATURE_FLAGS |
| `health.mock.ts` | 54 | MOCK_SERVICE_HEALTH |
| `incidents.mock.ts` | 55 | MOCK_INCIDENTS |
| `users.mock.ts` | 149 | MOCK_USERS, MOCK_USER_ACTIVITIES |

**Mock-data finding:** source searches for the directory/file imports and exported mock identifiers found no consumers outside these files in Angular source, including specs, and no matching imports in the other frontend source. These seven files are dead application/test data under the current import graph; they are not supplying the gateway-backed UI. AuthService's inline offline fallback remains live and is a separate concern. No files are removed by this inventory.

**statsChanged$ finding:** in Angular source there are exactly two references: declaration at `core/services/admin-api.service.ts:36` and subscription at `pages/dashboard/dashboard.component.ts:192`. There is **no `.next()` / emission site**. Thus the subscription would refresh dashboard cards only if emitted, but current Angular mutations never cause that refresh. The mutable mock stats/storage and their formatter are not imported and do not emit it. React's similarly intended stats-only event hook does not imply an Angular emission exists.

## 3. Angular unit specs and Karma retirement

Static count: **13 spec files, 82 `it(...)` cases, 1,193 physical lines**. This is an inventory of declared tests, **not a passing test result**. No Karma run was performed for this documentation task.

Spec paths below are relative to `src/app/`.

| Spec file | Lines / cases | Existing coverage and limitations |
| --- | ---: | --- |
| `core/guards/auth.guard.spec.ts` | 40 / 2 | Unauthenticated denial/login navigation (router spy) and authenticated access with a token in localStorage. |
| `core/interceptors/jwt.interceptor.spec.ts` | 45 / 2 | Local 401 logs out; peer-context 401 preserves the local session. Keep the peer case when migration moves. |
| `core/services/admin-api.service.spec.ts` | 151 / 13 | Construction plus nominal stats/users/user/audit/features/health/announcements/analytics/toggle/suspend cases; last two cases explicitly flush and assert incident PATCH/DELETE. Older nominal cases subscribe then tick 700 ms **without flushing HTTP**, so callback assertions do not establish data/mapping coverage. The dormant `activeDocuments > 0` expectation also conflicts with today's zero mapper. |
| `core/services/auth.service.spec.ts` | 120 / 9 | Initial state, offline fallback, gateway token, storage, logout, currentUser observable, token getter, empty-password rejection. Gateway success/failure requests are explicitly flushed/errored. |
| `core/services/migration-api.service.spec.ts` | 43 / 4 | Reconciliation base/encoded export URLs, local/peer archive URLs, peer config slash normalization and missing-config fallback, with HTTP verification. |
| `layout/sidebar/sidebar.component.spec.ts` | 65 / 7 | Creation, expanded state, navigation entries (including expected routes), collapse toggle and rendered sidebar/logo. |
| `pages/dashboard/dashboard.component.spec.ts` | 57 / 5 | Creation/loading/title plus expected loaded stats/four cards. Uses real service + HTTP testing module, ticks without HTTP flush; loaded-state assertions are not backed by a response. |
| `pages/health/health.component.spec.ts` | 56 / 5 | Creation/loading, load/count totals/title. Also ticks without HTTP flush, so actual load coverage needs repair rather than assuming historical mock data still arrives. |
| `pages/incidents/incidents.component.spec.ts` | 193 / 13 | Service spies; default closed visibility, closed/active filtering and counts; resolve/close/delete API calls, list removal and dialog-cancel paths. Does not establish polling, create/trigger-session, chaos or auto-investigation behavior. |
| `pages/login/login.component.spec.ts` | 55 / 5 | Creation, empty form, invalid submission, form elements and title; not end-to-end successful login. |
| `pages/migration/migration.component.spec.ts` | 132 / 5 | Latest report/summary/failures and authenticated CSV Blob, stale-run response cancellation, rule filtering, no-migration namespace hint, archive route param forwarding. Uses flushed requests. |
| `pages/migration/archive-compare.component.spec.ts` | 173 / 6 | Peer config/direct requests, same-origin proxy reads, field/event mismatches, missing versions, missing hash preventing match, 404 feature-off hint/no-peer verdict. Uses flushed requests. |
| `pages/users/users.component.spec.ts` | 63 / 6 | Creation/loading, expected data/columns, text-filter string, title; load uses ticks without HTTP flush. Does not cover the full filter/paginator/dialog/mutation contract. |

No adjacent unit specs exist for user-detail, audit, features, announcements, quotas, analytics, toolbar, AppComponent or the shared confirm dialog. Models/styles/mock-data have no dedicated specs either.

### What retirement requires

1. **Do not remove Karma yet.** Unported routes still depend on Angular, and React deliberately links to them. Shared Playwright parity currently covers login/dashboard/users, not the remainder or peer/cross-origin behavior. Existing React mapper unit tests are not replacements for every Angular service/spec.
2. Establish meaningful coverage before using the old suite as a baseline: replace unflushed mock-era HTTP expectations with explicit raw-response fixtures and HTTP verification or controlled service spies; reconcile stale expectations against actual Angular behavior, not historical mocks. Preserve deliberately specified quirks rather than “repairing” application behavior. This inventory identifies these gaps statically; it does not claim an observed Karma failure count.
3. For each remaining page, port behavior and migrate the relevant tests to React/Vitest and shared Playwright contracts: normal, empty/error, validation, filters/sort/pagination, dialogs/cancel paths and mutation refreshes. Add coverage for untested pages and operational incident actions, including polling cleanup and mock-safe chaos/Devin triggers.
4. Carry forward auth storage/fallback/guard/logout and **local vs peer 401** contracts; peer config caching/fallback, proxy-vs-cross-origin URLs, mismatch/hash/404 semantics, stale-run cancellation and authenticated exports need explicit equivalents before removing migration tests. Extend deterministic fixtures/mocks without invoking real chaos or session triggers.
5. Replace all legacy links, detail placeholders and deep links, and migrate shared shell/dialog/theme/bootstrap dependencies. Keep Angular deploy/proxy/peer configuration until no runtime consumers remain; deleting a unit runner does not by itself retire the Angular deployment.
6. Once coverage and cutover are accepted, remove/replace the Karma target in `angular.json`, `karma.conf.js`, `tsconfig.spec.json`, Angular/Jasmine test files and test-only dependencies/scripts in `package.json`/lockfile as appropriate. Current command is `npm test` → `ng test --watch=false --browsers=ChromeHeadless`; Karma also defines a `ChromeHeadlessNoSandbox` launcher, but the npm script overrides the browser choice. Any pre-retirement run needs an appropriate Chrome binary/launcher for the environment.
7. Update the Angular job in `.github/workflows/ci.yml` (currently `npm test || true`, so it is not an enforced retirement gate), the root Makefile's Angular test target, and the `admin-parity` job's Angular installation/server/project only at the agreed end of the comparison period. Make React replacement checks required rather than silently losing coverage. This document changes none of that wiring.

## Which two pages, and why

There is no page-level usage telemetry for the admin app. Navigation is client-side, ingress-nginx access logs on `otterworks-dev` are not retained (the controller had restarted minutes before this was checked), and nothing in the repo or Prometheus records admin page views. The pick is therefore a proxy, not a measurement:

- **Dashboard (`/`)** is the post-login landing route, so every admin session loads it.
- **Users (`/users`)** is the first nav item and the only page that the user-management flows (suspend, restore, delete) run through. It is also the page with the most legacy Selenium coverage.

Login and the shell (sidebar, toolbar, guard, JWT handling) were ported too, because the two pages cannot be used without them. These are one-time costs that the remaining pages do not pay again.

## Estimate

### What the two pages actually took

| Item | Angular lines | React lines written | Agent build time |
| --- | ---: | ---: | --- |
| Shell + auth + API client/mappers (one-time) | 296 + 159 + 95 | 387 | about 4 min, included in the first pass below |
| Login | 167 | 109 | (same pass) |
| Dashboard | 230 | 184 | (same pass) |
| Users (+ confirm dialog) | 271 + 38 | 578 | (same pass) |
| First working pass | | | 3 min |
| Rewrite to client-app conventions after review | | | 4 min |
| Shared Playwright parity suite (17 tests x 2 apps) + fixture gateway + CI job | | 547 | 4 min |
| Unit tests for the mappers | | 136 | (in the first pass) |

The time it took to write the code was small. The cost was in pinning down the behavior contract first: reading every quirk out of the Angular code and running it. That included the 5-row default page size, no default sort, search that matches only name and email, an infinite spinner on error, and a mock-login fallback. The parity suite was then needed to prove the React side matched. **No behavior differences turned up once the contract was written down.** The suite found zero mismatches, which shows that writing the spec first is what made the port safe.

Per page, React came out at about **0.8x (Dashboard) to 1.9x (Users)** the Angular line count, about 1.3x overall. Material gave Angular its table, paginator, sort, menu and dialog for free, and React had to write them. Users needed 578 lines for that reason. That code is now reusable by Audit, Quotas and User detail.

### The rest of the port

The remaining pages are **2,945 Angular lines**, about **4.4x** the three pages ported here (668). Two of them are disproportionately risky:

- **Incidents (710 lines, XL):** polling, chaos triggers, Devin session triggers and auto-investigate. These need fixture-safe stubs before they can be tested at all.
- **Migration + archive-compare (758 lines, XL):** peer-deployment config read from `/config/peer.json`, written by nginx. They also need the `PEER_REQUEST` 401 exemption and cross-origin comparison. This means deployment wiring (nginx, Helm), not just page code.

| Work package | Pages | Size | Human engineer-days | Devin sessions (plus human review) |
| --- | --- | --- | ---: | ---: |
| A. Table pages, reusing the Users table, paginator and dialog | Audit, Quotas, User detail | M, M, L | 4-5 | 1 |
| B. Simple CRUD / status pages | Features, Health, Announcements | S, M, M | 3-4 | 0.5-1 |
| C. Charts | Analytics (5 charts) | L | 1.5-2 | 0.5 |
| D. Incidents, with safe stubs for chaos and Devin triggers | Incidents | XL | 4-5 | 1 |
| E. Migration + archive-compare, peer config, nginx/Helm wiring | Migration, Archive-compare | XL | 4-6 | 1-1.5 |
| F. Cutover: serve `/admin` from the client-app image, redirect old deep links, retire the Angular image/Helm chart, Karma and the CI job, delete dead mock-data (528 lines) | - | - | 3-4 | 1 |
| **Total** | | | **20-26 engineer-days** (about 5 weeks for one engineer, 3 calendar weeks for two) | **5-6 sessions, one PR per package** |

How the numbers were derived:

- **Human days:** I estimate the work in this PR at about 4-5 engineer-days for one engineer who knows both stacks: shell/auth about 1.5, Dashboard about 1, Users about 1.5, parity harness about 1. That is my judgement, not a measurement. Scaling the page work by 4.4x, adding about 30% for the two XL pages and about 0.5 day per page for parity tests, and adding the cutover gives the range above.
- **Devin sessions:** the build time above is real, but most of a session goes to setup, contract discovery, review rounds and recordings. Human PR review (about half a day per package) is the bottleneck, not writing code.
- **What would move it:** (1) the risky part is E's deployment wiring. Its peer behavior can only be fully verified on a deployed tenant pair, not locally. (2) These estimates are against a deterministic fixture gateway, not the real admin-service. On the `main` tenant the admin-service crash-loops (a known planted bug), so a real-backend check needs a `workshop-*` tenant. (3) Several faithfully preserved quirks, listed in the PR, look like bugs. Fixing them during the port would add scope and break parity, so the plan is to port first and fix afterwards.
