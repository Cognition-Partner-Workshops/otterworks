# Migrated client Playwright tests

These tests use real local services, not intercepted network responses. Each test
registers a unique API user, seeds the four source screenshot documents, verifies
the API total, and initializes browser auth tokens. See [Documents parity](documents/PARITY.md),
[Authentication parity](authentication/PARITY.md), [Search parity](search/PARITY.md),
[Settings parity](settings/PARITY.md), and [Sharing parity](sharing/PARITY.md).
Authentication tests register a disposable user (or none) and need no backend beyond
the stack below.

The combined legacy migration decisions and 20-test inventory are documented in
[CROSSCHECK.md](CROSSCHECK.md) and [LEGACY-MIGRATION.md](LEGACY-MIGRATION.md).

## Prerequisites

Start from a fresh clone on this branch with Docker Engine/Compose v2, Node.js
22.12+ (required by Vite 8), npm, and curl installed. Commands below assume Bash
and start at the repository root. Ports 3000, 5432, 6379, 4566, 7700, 8080–8083,
and 8087 must be available. No AWS credentials or cloud services are required.

## Build and start the real backend

Docker Hub returned unauthenticated pull-rate limits during migration. Pull and
tag the same base images from Google's registry mirror first:

```bash
for image in postgres:15-alpine redis:7-alpine \
  gradle:8.6-jdk17 eclipse-temurin:17-jre-jammy python:3.12-slim \
  rust:latest debian:trixie-slim golang:1.22-alpine alpine:3.19
do
  docker pull "mirror.gcr.io/library/$image"
  docker tag "mirror.gcr.io/library/$image" "$image"
done
docker pull mirror.gcr.io/localstack/localstack:3.8
docker tag mirror.gcr.io/localstack/localstack:3.8 localstack/localstack:3.8
docker pull mirror.gcr.io/getmeili/meilisearch:v1.6
docker tag mirror.gcr.io/getmeili/meilisearch:v1.6 getmeili/meilisearch:v1.6
```

The normal auth-service build hit Maven Central HTTP 429. This alternative image
build uses the unchanged auth-service sources and adds Google's Maven Central
mirror through a Gradle init script. Run from the repository root; no external
files or source copying are needed:

```bash
docker build \
  -f frontend/client-app/e2e/migrated/stack/auth-service-mirror.Dockerfile \
  -t otterworks-auth-service .

docker compose -f docker-compose.infra.yml -f docker-compose.yml \
  build document-service file-service api-gateway search-service

docker compose -f docker-compose.infra.yml -f docker-compose.yml \
  up -d --no-build postgres redis localstack meilisearch \
  auth-service document-service file-service api-gateway search-service

docker compose -f docker-compose.infra.yml -f docker-compose.yml ps
```

Wait for all nine containers to be healthy before running tests. The gateway's
health endpoint alone does not prove auth has finished its database migrations.
Check the HTTP services explicitly (curl retries only on errors):

```bash
for port in 8080 8081 8082 8083 8087 7700; do
  curl --fail --silent --show-error --retry 30 --retry-all-errors \
    --retry-delay 2 "http://localhost:$port/health"
  printf '\n'
done
```

The documents list/editor uses `/api/v1/documents` and auth through the gateway.
Dashboard statistics additionally require `/api/v1/files` and `/api/v1/files/activity`;
file-service uses LocalStack for its AWS-backed storage. PostgreSQL and Redis are
local Compose infrastructure. Do not replace these endpoints with mocks.

Search requests go through `/api/v1/search` to `search-service`, which queries
MeiliSearch. Indexing is asynchronous: document-service and file-service publish
events to SNS `otterworks-events`, which delivers them to SQS
`otterworks-search-events`. `scripts/localstack-init.sh` creates the topic, queue,
and subscription and is mounted into LocalStack. The migrated `support/search.ts`
polls the real search API until every seeded document and file is indexed before
the browser test starts.

## Serve the client

In a terminal from the repository root:

```bash
cd frontend/client-app
npm ci
npx playwright install chromium
npm run dev -- --host 0.0.0.0 --port 3000
```

Leave Vite running. Its same-origin `/api/v1` proxy forwards to the gateway on
localhost:8080. On Linux hosts missing Chromium system libraries, provision them
with `npx playwright install-deps chromium` (requires system package permissions).

## Run the suite

In a second terminal from the repository root:

```bash
cd frontend/client-app
curl --fail http://localhost:3000
npm run test:e2e:migrated
# One converted Tosca case:
npm run test:e2e:migrated -- --grep '@TC-DOC-003'
npm run test:e2e:migrated -- --grep '@TC-SRCH-001'
# Verification used for this migration:
npm run lint
npx tsc --noEmit
npm run test:e2e:migrated
npm run test:e2e:migrated
# Confirm the old config excludes migrated specs (list only, not execution):
npx playwright test --list
```

The migrated config reuses the running server. Reports are written to
`frontend/client-app/playwright-report-migrated/index.html` (HTML and JSON results),
with failure screenshots/traces in `playwright-report-migrated-artifacts/` beside
it. Both directories are ignored by Git. View HTML with
`npx playwright show-report playwright-report-migrated` from the client directory.

Leave the stack and Vite running for further checks. Disposable users/documents
remain in the local Compose data volumes; tests do not reuse their accounts.
