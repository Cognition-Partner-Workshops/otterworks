# Migrated admin Playwright suite

This is a real-service Playwright suite for the admin dashboard's five migrated
Selenium modules. For the shared migration decisions and full 20-test inventory,
see [CROSSCHECK.md](../../../client-app/e2e/migrated/CROSSCHECK.md) and
[LEGACY-MIGRATION.md](../../../client-app/e2e/migrated/LEGACY-MIGRATION.md).
For the client app's parallel harness and behavior, see the
[client migrated Playwright runbook](../../../client-app/e2e/migrated/README.md).

## Prerequisites

Start from the repository root with Docker Engine and Compose v2, `curl`, `nvm`,
and npm available. Use Node 20 for this Angular 17 app and Node 22.12+ for the
client app (Vite 8). The combined local stack needs ports 3000, 4200, 5432,
6379, 4566, 7700, 8080–8083, 8087, and 8089 available. No cloud credentials
are required.

## Build and start the real backend

The local Compose setup used Google registry mirrors for Docker Hub base images
and the client's auth-service mirror Dockerfile for its Gradle build. From the
repository root:

```bash
for image in postgres:15-alpine redis:7-alpine \
  gradle:8.6-jdk17 eclipse-temurin:17-jre-jammy python:3.12-slim \
  rust:latest debian:trixie-slim golang:1.22-alpine alpine:3.19 \
  ruby:3.3-slim
do
  docker pull "mirror.gcr.io/library/$image"
  docker tag "mirror.gcr.io/library/$image" "$image"
done
docker pull mirror.gcr.io/localstack/localstack:3.8
docker tag mirror.gcr.io/localstack/localstack:3.8 localstack/localstack:3.8
docker pull mirror.gcr.io/getmeili/meilisearch:v1.6
docker tag mirror.gcr.io/getmeili/meilisearch:v1.6 getmeili/meilisearch:v1.6

docker build \
  -f frontend/client-app/e2e/migrated/stack/auth-service-mirror.Dockerfile \
  -t otterworks-auth-service .

docker compose -f docker-compose.infra.yml -f docker-compose.yml \
  build document-service file-service api-gateway search-service admin-service

docker compose -f docker-compose.infra.yml -f docker-compose.yml \
  up -d --no-build postgres redis localstack meilisearch auth-service \
  document-service file-service api-gateway search-service admin-service

docker compose -f docker-compose.infra.yml -f docker-compose.yml ps

for port in 8080 8081 8082 8083 8087 8089 7700; do
  curl --fail --silent --show-error --retry 30 --retry-all-errors \
    --retry-delay 2 "http://localhost:$port/health"
  printf '\n'
done
```

Leave the Compose stack running. In the validated partial stack, auth, file, and
document were healthy; the admin health API reported `degraded` because collab,
notification, search, analytics, and audit were unavailable.

### Optional local seed data

Rails' admin-service seed creates three feature flags; it did not create
`admin_users` rows or audit-log rows:

```bash
docker compose -f docker-compose.infra.yml -f docker-compose.yml \
  exec -T admin-service bundle exec rails db:seed
```

The root-level Python seed is also optional and was not run during this
validation. From the repository root, `uv run scripts/seed.py` inserts ten
`admin_users`, storage quotas, audit entries, feature flags, and announcements
using the local Compose database defaults. Both seed paths mutate local data;
neither is required to run the Playwright harness.

## Serve both frontends

Use separate terminals from the repository root. Leave both servers running:

```bash
# Admin Angular app, Node 20
cd frontend/admin-dashboard
nvm use 20
npm ci
npx playwright install chromium
npm run start
```

```bash
# Client Vite app, Node 22.12+
cd frontend/client-app
nvm use 24
npm ci
npx playwright install chromium
npm run dev -- --host 0.0.0.0 --port 3000
```

The admin server listens on `http://localhost:4200`; its `/api` proxy targets
the gateway at `http://localhost:8080`. The client server listens on
`http://localhost:3000`. The [client runbook](../../../client-app/e2e/migrated/README.md)
has its own stack and test details.

Angular's root TypeScript config must not pull the Playwright config or E2E
helpers into its application compilation. The admin `tsconfig.json` excludes
those files, while `tsconfig.e2e.json` type-checks them separately. No
`@types/node` version pin was needed in the validated environment.

## Run the migrated Playwright configs

From each app directory, use its own config and npm script:

```bash
# Admin dashboard, Node 20
cd frontend/admin-dashboard
npx playwright test --config playwright.migrated.config.ts --list
npm run test:e2e:migrated
# Optional case filter after a tagged spec is added:
npm run test:e2e:migrated -- --grep '@<ID>'
# Override the admin app base URL (default http://localhost:4200):
ADMIN_BASE_URL=http://localhost:4200 npm run test:e2e:migrated
```

```bash
# Client app, Node 22.12+
cd frontend/client-app
npx playwright test --config playwright.migrated.config.ts --list
npm run test:e2e:migrated
npm run test:e2e:migrated -- --grep '@<ID>'
```

The admin config uses Chromium, no retries, and retain-on-failure traces and
screenshots. HTML and JSON reports are written under
`playwright-report-migrated/`; failure artifacts are written under
`playwright-report-migrated-artifacts/`. Both directories and `test-results/`
are ignored by Git. The admin config starts `npm run start` if the server is not
already available at port 4200.

### Admin helper API

`e2e/migrated/support/admin-session.ts` exports:

- `registerGatewayUser`: registers a unique `@example.com` gateway user and
  checks the returned email, JWT subject, and non-mock ID.
- `signInAdminSession`: registers a user, proves its token can read
  `/api/v1/admin/users`, and initializes the same localStorage values as
  `AuthService.gatewayLogin`.
- `waitForAdminApi` and `openAdminPage`: prove protected page/action requests
  carry the real registered gateway token; `expectGatewaySession` rejects the
  offline mock session.
- `signInThroughLoginForm`: exercises the real labeled login inputs and verifies
  the resulting gateway session.
- `matSelect` and `typeIntoFilter`: shared Angular Material and keyup-filter
  helpers; `uniqueFlagName` gives each feature flag a non-colliding name.
- `createFeatureFlag` and `deleteFeatureFlag`: use the real admin API; the
  `adminData` fixture tracks created flags and deletes them during teardown.
- `OFFLINE_MOCK_USER_ID`, `GatewayUser`, `AdminSession`, and `adminTest`.

These helpers call live gateway/admin APIs and do not intercept requests. The
admin service verifies JWT signatures but does not enforce user roles, so a
freshly registered USER-role token was accepted by the admin endpoints. The
helper does not use the dashboard's offline mock session.

### Observed admin API behavior

The validated calls queried `/api/v1/admin/users`, `/api/v1/admin/audit-logs`,
`/api/v1/admin/features`, `/api/v1/admin/health/services`, and
`/api/v1/admin/metrics/summary` through both `:8080` and `:4200`. A registered
gateway user's token received HTTP 200 for all five endpoints at each stage:

| Stage | Admin users | Audit logs | Features | Health |
|---|---:|---:|---:|---|
| Fresh database | 0 | 0 | 0 | `degraded`, 3/8 healthy |
| After Rails `db:seed` | 0 | 0 | 3 | `degraded`, 3/8 healthy |
| After two more gateway registrations | 0 | 0 | 3 | `degraded`, 3/8 healthy |
| After helper feature creation | 0 | 5 | 4 | `degraded`, 3/8 healthy |

Gateway registrations did not populate the distinct `admin_users` table. A
feature created by `adminData.createFeatureFlag()` appeared in the audit API as
`feature_flag.created`; the fixture deleted the feature after checking it.

No-token requests returned 401 for all endpoints through both origins. The
built-in offline mock token unexpectedly returned 200 for all endpoints through
both origins, rather than the anticipated 401. This is the observed result on
the local development stack; application/service code was not changed to alter
it. Keep migrated tests on freshly registered gateway users.

Detailed status/body summaries are saved outside the repository at
`~/scaffold-evidence/admin-api-probes.md`.

## Legacy suites (detached worktree)

The legacy files are evidence and must remain untouched. From the repository
root, create/use the detached worktree:

```bash
git worktree add ../otterworks-legacy origin/qe/legacy-suites-fixture
```

Maven was not preinstalled in the validation environment. Install Maven 3.9.9
from the Google Maven Central mirror and make it available in `PATH`:

```bash
mkdir -p "$HOME/.local"
curl -fsSLo "$HOME/.local/apache-maven-3.9.9-bin.tar.gz" \
  https://maven-central.storage-download.googleapis.com/maven2/org/apache/maven/apache-maven/3.9.9/apache-maven-3.9.9-bin.tar.gz
tar -xzf "$HOME/.local/apache-maven-3.9.9-bin.tar.gz" -C "$HOME/.local"
export PATH="$HOME/.local/apache-maven-3.9.9/bin:$PATH"
mvn -version
```

The committed
[`stack/maven-settings.xml`](stack/maven-settings.xml) mirrors Maven Central
to Google's mirror. Run Selenium from its worktree directory:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
cd ../otterworks-legacy/tests/legacy-suites/selenium
ADMIN_BASE_URL=http://localhost:4200 \
  mvn -s "$REPO_ROOT/frontend/admin-dashboard/e2e/migrated/stack/maven-settings.xml" test
# Optional single-class run:
ADMIN_BASE_URL=http://localhost:4200 \
  mvn -s "$REPO_ROOT/frontend/admin-dashboard/e2e/migrated/stack/maven-settings.xml" \
  -Dtest=UsersTest test
```

Chrome for Testing was available at `~/.local/bin/google-chrome`. Selenium 4.21
Selenium Manager selected a matching ChromeDriver automatically (Chrome and
ChromeDriver 156.0.8078.47); no manual driver path was needed.

Run Cypress from the separate legacy worktree with the client Vite server still
running on port 3000:

```bash
cd ../otterworks-legacy/tests/legacy-suites/cypress
npm install --no-package-lock
npm run test:e2e
```

Cypress 13.17.0 downloaded and verified its binary automatically, then ran in
headless Electron; no xvfb setup was needed in this environment. The actual
legacy results (including failures, which were not fixed) are recorded at
`~/scaffold-evidence/legacy-runs.md`.

## Lint

The admin package's `npm run lint` invokes `ng lint`, but this Angular project
has no lint target configured. Run it to observe the exact missing-target
message; do not add a lint target solely for this scaffold. The observed output
was:

```text
> @otterworks/admin-dashboard@0.1.0 lint
> ng lint

Cannot find "lint" target for the specified project.
You can add a package that implements these capabilities.

For example:
  ESLint: ng add @angular-eslint/schematics
```

The client lint command and result are covered by the
[client runbook](../../../client-app/e2e/migrated/README.md). In this
validation, the legacy Selenium worktree had 4 passing and 11 failing tests;
the Cypress worktree had 5 passing tests and no failures. See
`~/scaffold-evidence/legacy-runs.md` for the details and raw-log paths.
