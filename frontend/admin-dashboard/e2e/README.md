# Admin dashboard Playwright suite

Daily admin workflows against the **real** local gateway and Rails admin API.
No Tosca export, backend mocks, incidents/chaos/session launches, migration data,
analytics canvas assertions, or seeded-user deletion. No app/backend source changes.
Do not fix the planted production logger bug: use the existing development Compose service.

## Start the stack

From the repository root (Docker Compose v2 with BuildKit named build contexts):

```sh
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d postgres redis localstack
docker compose -f docker-compose.infra.yml -f docker-compose.yml build api-gateway admin-service file-service document-service

docker build --build-context mirror=frontend/admin-dashboard/e2e/stack \
  -f frontend/admin-dashboard/e2e/stack/auth-service-mirror.Dockerfile \
  -t otterworks-auth-service .
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --no-build \
  api-gateway auth-service admin-service file-service document-service

# Optional generic demo rows; tests never depend on or mutate these rows.
uv run scripts/seed.py

docker compose -f docker-compose.infra.yml -f docker-compose.yml build collab-service search-service
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --no-build collab-service search-service
docker compose -f docker-compose.infra.yml -f docker-compose.yml build audit-service
docker build --build-context mirror=frontend/admin-dashboard/e2e/stack \
  -f frontend/admin-dashboard/e2e/stack/report-service-mirror.Dockerfile \
  -t otterworks-report-service .
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --no-build audit-service report-service

# Attempt the remaining health-probed services when Maven/Scala repositories allow it:
docker compose -f docker-compose.infra.yml -f docker-compose.yml build notification-service analytics-service
docker compose -f docker-compose.infra.yml -f docker-compose.yml up -d --no-build notification-service analytics-service
```

The auth Gradle init and report Maven settings use Google Maven Central mirrors.
These four files in `stack/` are the mirror build files used for the route inventory.
If Docker Hub is rate limited, pull/tag the affected base image first, for example:

```sh
docker pull mirror.gcr.io/library/gradle:8.6-jdk17
docker tag mirror.gcr.io/library/gradle:8.6-jdk17 gradle:8.6-jdk17
```

Repeat for the base image named in the failing build. The mirror did not offer
`eclipse-temurin:8-jre`; `docker pull eclipse-temurin:8-jre` worked locally.
Notification's Gradle shadowJar and analytics' sbt assembly hit Maven HTTP 429 locally;
they remain down. **No mocks** replace them. Health tests compare current probe statuses,
including unhealthy/degraded services, rather than expecting a fixed list of healthy services.
All other thirteen containers were healthy during inventory. Report-service is healthy
but ARCHIVE_STORE is unset; migration/archive tests are intentionally out of scope.

In a separate terminal:

```sh
cd frontend/admin-dashboard
source "$HOME/.nvm/nvm.sh"
nvm install 20
nvm use 20
npm ci
npx playwright install chromium
npm run start -- --host 0.0.0.0
```

Leave this terminal and the Compose services running. Gateway: http://localhost:8080;
Angular: http://localhost:4200. Existing `proxy.conf.mjs` forwards /api to the gateway.
Set `API_GATEWAY_URL` when starting Angular to use a different gateway.
No `@types/node@20.19.9` pin was necessary locally.

## Run

From `frontend/admin-dashboard` under Node 20:

```sh
npm run test:e2e
npm run test:e2e -- --grep @ADM-USR-001
npm run test:e2e -- --headed
npx tsc --noEmit -p tsconfig.e2e.json
npx ng build
```

`ADMIN_BASE_URL` overrides the default frontend URL. The config reuses an existing
server; if absent it starts `npm run start` on 4200. For a non-default URL, start
that server separately. Two workers keep load modest while preserving fully parallel
test isolation; retries are zero. HTML: `playwright-report/index.html`; JSON:
`playwright-report/results.json`; traces/screenshots on failure: `test-results/`.
Reports/artifacts are ignored. They may contain live local session tokens; do not commit
or publish raw traces. Inspect JSON `expectedStatus` and result `status`: expected
failures are not successful app behavior, even though the suite exits successfully.

## Isolation and cleanup

Every test registers a fresh uniquely named gateway user using the real register API.
Form tests log in through the UI; other tests install that exact registered identity
and access token once per browser tab via addInitScript. Session identity is checked
against the issued token and registered user ID, never inferred from an admin 200.
Admin-service verifies JWT signatures but does not enforce admin roles.

Features and announcements are created through the real admin API and deleted in
fixture teardown (including after failures). Flags use `aaa_e2e_<uuid>` snake_case
names so they sort ahead of generic seed flags on the API's first page (20 rows).
Audit tests search their own flag's unique description/resource UUID. List searches
use pressSequentially because the app listens to keyup.

**One non-API seed:** admin_users has no create endpoint. Verified
`config/routes.rb`, UsersController (index/show/update/destroy/suspend/activate),
BulkController and BulkOperationsService: bulk operations only update existing users.
`e2e/users/fixtures.ts` inserts one UUID admin_users row and its storage_quotas row
in a transaction using `docker exec ... psql`, with columns from
`services/admin-service/db/schema.rb`. It hard-deletes only that UUID/email and its
quota/audit rows in teardown. It does not call seed.py or modify seed rows.

Database cleanup also removes the fresh gateway user (auth exposes no delete-user API;
refresh tokens/roles cascade) and audit rows generated by that test's actor ID.
API cleanup is used for features/announcements. These are local fixtures only.

Database command environment knobs, defaulting to Compose:
- `ADMIN_PG_CONTAINER=otterworks-postgres`
- `ADMIN_PG_USER=otterworks`
- `ADMIN_PG_DATABASE=otterworks`

Requires local Docker exec access; never point this suite at production/shared data.
All inserted string literals are SQL-escaped; Docker is called with an argument array,
not interpolated shell commands. Empty/error states are asserted rather than mocked.

## Locator and traceability conventions

Each case has an ADM identifier, area tag, screen annotation and admin-action test steps.
Use roles/labels, scope to rows/dialogs/cards, and auto-retrying UI assertions.
Material cards lack region roles, so tests scope using the semantic `mat-card` element
and its heading/label, never CSS classes or IDs. Unnamed feature switches are then
located by switch role inside their own card. Role-less summary divs include decorative
icon ligatures; their exact text pattern is documented inline. Error/status/value text
locators carry accessibility-gap comments. No XPath, nth chains, sleeps, visibility
branching or response mocking.

The dashboard comparison captures its real metrics response in-test to compare the
same snapshot rendered by the page; a separate request could race another parallel
test's user-fixture creation/teardown.

## Known app defects

These were first run with ordinary assertions and failed on the real stack, then
marked test.fail(). The suite keeps faithful assertions and never patches src/ or
backend code. A fix that makes one pass becomes an unexpected pass and fails the suite.

| Test | Evidence / defect |
|---|---|
| ADM-AUTH-003 | Gateway rejects wrong password with HTTP 400; browser nevertheless navigates to dashboard as offline Admin User. auth.service.ts:53 catches gateway errors and mockLogin at :93-107 accepts non-empty passwords/stores the mock token. Rejection/error/no-token assertions remain. |
| ADM-FEAT-002 | Second toggle looks checked, but GET still returns enabled=false. features.component.ts:133-141 computes !flag.enabled without updating flag.enabled after saving; both PUTs send false. |
| ADM-QUOTA-001 | API GET confirms quota_bytes=10737418240, but UI Quota cell remains 5 GB (dropdown alone shows 10 GB). quotas.component.ts:175-178 only shows a snackbar after saving; it never updates user.storageQuota. The assertion requires the actual Quota cell to show 10 GB. |

The remaining twelve tests should pass. Notification/analytics health failures are
valid probe data, not expected-failure cases. A gateway login 400 is the existing
auth-service credential-rejection contract, not an assertion relaxed to accept login.
