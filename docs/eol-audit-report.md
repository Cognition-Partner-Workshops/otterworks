# EOL / outdated dependency audit

Audit date: 2026-11-02. Scope: `main` at `0fe3e15c5`, plus `mise.toml` and the
branch-only deltas on `tech-partnerships` (`32baffd86`), because `mise.toml` exists only there.
This is an audit only: no dependency versions were changed.

Sources: EOL dates from [endoflife.date](https://endoflife.date) (API, read 2026-11-02);
"latest stable" from the npm registry, PyPI and GitHub releases on the same day.
**Legacy (by design)** marks components that are the intentional "before" state of an
upgrade demo (see `etl/ETL_UPGRADE_GUIDE.md`, `clients/windows-desktop/README.md`); they
are reported for completeness and are not upgrade candidates without an explicit decision.

Status key: **EOL** = past upstream end of life; **EOL < 90d** = support ends within 90 days;
**Behind** = supported but one or more majors behind; **OK**.

## Summary

| Priority | Finding | Where |
|---|---|---|
| P0 | .NET 8 reaches EOL on **2026-11-10** (8 days after this audit) | `services/audit-service`, `ci.yml` |
| P0 | Node.js 20 EOL since 2026-04-30 | 6 Dockerfiles, `platform/standards/base-images.yaml`, 8 CI jobs |
| P0 | Go 1.22 EOL since 2025-02-11 | `go.mod`, `api-gateway/Dockerfile`, `ci.yml`, `codeql.yml` (+2 on `tech-partnerships`) |
| P0 | Angular 17 EOL since 2025-05-15 | `frontend/admin-dashboard` |
| P0 | Spring Boot 3.2 (OSS) EOL since 2024-12-31 | `services/auth-service` |
| P0 | Rails 7.1 EOL since 2025-10-01 | `services/admin-service` |
| P1 | EOL base images: `alpine:3.19`, `alpine:3.20`, `nginx-unprivileged:1.25/1.27`, `postgres:15-alpine` | see §4 |
| P1 | EOL observability stack: Prometheus 2.51, Grafana 10.4, Jaeger 1.55 (v1 line), Fluent Bit 3.0, Meilisearch 1.6/1.8 | `docker-compose.infra.yml`, `scripts/deploy-tenant.sh` |
| P1 | Kotlin 1.9 and Scala 3.4 EOL | `notification-service`, `analytics-service` |
| P1 | ESLint 8 EOL (2024-10-05) | dashboard, otter-projects, client-app, collab-service |
| P1 | Terraform 1.15 (mise) and 1.9 (runner image) EOL; Helm 3 security fixes end 2026-11-11; kubectl 1.30 EOL | `mise.toml`, `demo-platform/runner/Dockerfile`, `scripts/tenant-platform-baseline.sh` |
| P1 | EKS 1.34 standard support ends 2026-12-02; module default 1.32 is already in extended (paid) support | `platform/terraform` |
| P2 | GitHub Actions: no v2/v3 actions and no `::set-output`, but every first-party action is 1-3 majors behind | §5 |
| — | No Django, no React 17, no webpack, no Python < 3.12 found anywhere in the repo | — |

## 1. `mise.toml` (exists on `tech-partnerships` only)

| Component | File | Current | Latest stable | EOL status | Recommended |
|---|---|---|---|---|---|
| terraform | `mise.toml` | 1.15.8 | 1.17.1 | **EOL** (1.15 EOL 2026-10-21; only the two newest minors are supported) | 1.17.x |
| tflint | `mise.toml` | 0.64.0 | 0.65.0 | Behind (minor) | 0.65.0 |
| checkov (pipx) | `mise.toml` | 3.3.11 | 3.4.2 | Behind (minor) | 3.4.x |
| check-jsonschema (pipx) | `mise.toml` | 0.38.0 | 0.39.0 | Behind (minor) | 0.39.0 |
| mongodb-atlas-cli | `mise.toml` | atlascli/v1.58.0 | v1.59.4 | Behind (minor) | v1.59.x |
| aws-cli | `mise.toml` | 2.36.24 | 2.39.3 | Behind (minor); v2 is current | 2.39.x |
| databricks cli (aqua) | `mise.toml` | 1.12.1 | not verified (GitHub org IP allow-list blocked the lookup) | Unknown | check `databricks/cli` releases |

`main` has no `mise.toml`, `.tool-versions`, `.nvmrc`, `.python-version` or `rust-toolchain`;
runtime versions on `main` are set only by Dockerfiles and CI.

## 2. `package.json` files

None of the six files declares an `engines` field (or `packageManager`), so nothing stops
installs on an EOL Node. Every project's Dockerfile and CI job uses Node 20.

| Component | File | Current | Latest stable | EOL status | Recommended |
|---|---|---|---|---|---|
| Node runtime (all six) | Dockerfiles / CI (see §4, §5) | 20 | 26.13.0 (LTS since 2026-10-28) | **EOL** 2026-04-30 | 24 LTS (EOL 2028-04-30) or 26 LTS; add `"engines": {"node": ">=24"}` |
| `@types/node` | all except admin-dashboard | 20.x | 26.6.6 | Behind | match the runtime major |
| next | `demo-platform/dashboard` | 15.5.20 | 16.4.4 | OK (15 EOL 2027-01-31) | 15.5.28 now, plan 16 |
| next | `demo-platform/otter-projects` | 15.5.21 | 16.4.4 | OK (15 EOL 2027-01-31) | 15.5.28 now, plan 16 |
| react / react-dom | dashboard, otter-projects, client-app | 18.3.1 / ^18.2.0 | 19.3.1 | Behind (18 no longer actively supported since 2024-12-05) | 19.x |
| eslint | dashboard, otter-projects, client-app, collab-service | 8.57.0 / ^8.57.0 | 10.14.0 | **EOL** 2024-10-05 (9.x also EOL 2026-08-06) | 10.x (flat config) |
| typescript | all six | 5.3-5.4 | 7.0.2 | Behind (2 majors) | 5.9 now, plan 7 |
| tailwindcss | dashboard, otter-projects, client-app | 3.4.x | 4.3.3 | OK (3.4 EOL 2027-02-28) | plan 4.x |
| @kubernetes/client-node | dashboard | 0.20.0 | 2.0.1 | Behind (2 majors) | 1.x/2.x |
| @aws-sdk/client-dynamodb, lib-dynamodb | dashboard, otter-projects | 3.556.0 | 3.1161.0 | Behind (v3 minor, ~2.5 years old) | latest 3.x |
| vitest | otter-projects | 2.1.8 | 5.1.0 | Behind (3 majors) | 5.x |
| react-markdown | otter-projects | 9.0.1 | 10.1.0 | Behind | 10.x |
| @angular/* (core, cli, material, ...) | `frontend/admin-dashboard` | ^17.3.0 | 22.2.4 | **EOL** 2025-05-15 | 21 (EOL 2027-06-30) or 22, via `ng update` one major at a time |
| zone.js | admin-dashboard | ~0.14.4 | 0.16.3 | Behind (tied to Angular) | with Angular |
| ng2-charts | admin-dashboard | ^5.0.3 | 11.0.0 | Behind (tied to Angular) | with Angular |
| karma + karma-* | admin-dashboard | ~6.4.3 | 6.4.4 | **Deprecated** upstream (Angular CLI moved off Karma) | plan Jest/Vitest/Web Test Runner with the Angular upgrade |
| vite | `frontend/client-app` | ^8.1.4 | 8.3.5 | OK | — |
| vitest | client-app | ^4.1.10 | 5.1.0 | Behind (1 major) | 5.x |
| @tiptap/* | client-app | ^2.2.4 | 3.32.2 | Behind (1 major) | 3.x |
| @testing-library/react | client-app | ^14.2.1 | 16.3.3 | Behind (2 majors) | 16.x (needed for React 19) |
| zustand / date-fns / recharts | client-app | 4 / 3 / 2 | 5 / 4 / 3 | Behind (1 major each) | latest majors |
| lucide-react | client-app | ^0.354.0 | 1.66.0 | Behind | 1.x |
| y-websocket | client-app | ^2.0.3 | 3.1.0 | Behind | align with collab-service |
| @capacitor/* | client-app | ^8.4.2 | 8.6.0 | OK | — |
| electron | `frontend/client-app/desktop` | 43.1.0 | 45.2.1 | OK but 2 majors behind (43 EOL 2027-01-05) | 43.8.6 now (patch), 45.x before Jan 2027 |
| electron-builder | desktop | ^26.15.3 | 26.18.0 | OK | — |
| express / @types/express | `services/collab-service` | ^4.18.3 | 5.3.0 | Behind (4.x still maintained) | 5.x |
| @opentelemetry/sdk-node, exporter, instrumentation-http | collab-service | ^0.49.1 | 0.300.0 | Behind (experimental line, very old) | latest, with `@opentelemetry/api` 1.10 / sdk 2.x |
| y-websocket (server) | collab-service | ^1.5.4 | 3.1.0 | Behind (2 majors; client uses 2.x) | align client and server |
| pino / pino-pretty | collab-service | ^8 / ^10 | 10.4.0 / 13.2.0 | Behind (2-3 majors) | latest |
| helmet / uuid | collab-service | ^7 / ^9 | 8.3.0 / 14.0.3 | Behind | latest |
| jest / ts-jest / @types/jest | collab-service | ^29 | 30.5.2 | Behind (1 major) | 30.x |
| @typescript-eslint/* | collab-service | ^7.1.1 | 8.72.1 | Behind (v7 unsupported) | 8.x with ESLint 10 |

## 3. Python (`requirements*.txt`, pyproject, Python pins)

Python pins: every Python Dockerfile uses 3.12 (`python:3.12-slim`, `python:3.12-slim-bookworm`,
`python:3.12-alpine`), CI uses `python-version: '3.12'`, and pyprojects say `^3.12` / `>=3.12`.
Python 3.12 is supported (security fixes only) until **2028-10-31**. **No Python < 3.9 and no
3.10 (EOL 2026-10-01) is pinned anywhere.** `etl/` has no Dockerfile or version pin
(`etl/run.sh` calls the host `python3`). **There is no Django in the repo.**

| Component | File | Current | Latest stable | EOL status | Recommended |
|---|---|---|---|---|---|
| pandas | `etl/requirements.txt` | 1.3.5 | 3.1.0 | **EOL** (1.x unsupported; no wheels for current Pythons) | Legacy (by design) |
| boto3 | `etl/requirements.txt` | 1.26.0 | 1.43.123 | Behind | Legacy (by design) |
| requests | `etl/requirements.txt` | 2.27.0 | 2.34.2 | Behind (pre-2.32.4 security fixes) | Legacy (by design) |
| psycopg2-binary | `etl/requirements.txt` | 2.9.3 | 2.9.13 | Behind (patch) | Legacy (by design) |
| Flask | `services/legacy-billing/app/requirements.txt` | 3.1.1 | 3.1.3 | OK (patch) | 3.1.3 |
| psycopg[binary] | legacy-billing/app | 3.2.9 | 3.3.6 | Behind (no cp314 wheel for 3.2.9) | 3.3.x |
| gunicorn | legacy-billing/app | 23.0.0 | 26.2.0 | Behind | latest |
| oracledb (`tech-partnerships` only) | legacy-billing/app | 2.5.1 | 26.1.0 | Behind | latest |
| flask | `services/search-service/requirements.txt` | 3.0.2 | 3.1.3 | Behind (minor) | 3.1.3 |
| flask-cors | search-service | 4.0.2 | 6.0.5 | Behind (2 majors) | 6.x; run `pip-audit` |
| gunicorn | search-service | 22.0.0 | 26.2.0 | Behind | latest |
| requests | search-service | 2.31.0 | 2.34.2 | Behind (pre-2.32.4 security fixes) | 2.34.x |
| marshmallow | search-service | 3.21.1 | 4.3.1 | Behind (1 major) | 4.x |
| meilisearch (client) | search-service | 0.31.6 | 0.43.0 | Behind (pairs with server v1.6/1.8, see §4) | upgrade with the server |
| opentelemetry-api/sdk, instrumentation-flask | search-service | 1.23.0 / 0.44b0 | 1.45.2 / 0.66b2 | Behind | latest matching pair |
| structlog / prometheus-client / redis | search-service | 24.1 / 0.20 / 5.0.4 | 26.1 / 0.26 / 8.1 | Behind | latest |
| boto3 / python-dotenv / urllib3 | search-service | 1.34.69 / 1.0.1 / 2.7.0 | 1.43.123 / 1.2.4 / 2.8.0 | Behind (minor) | latest |
| pytest / pytest-cov | search-service (+ `-dev`) | 8.1.1 / 5.0.0 | 9.2.0 / 7.1.0 | Behind | latest |
| httpx, pytest, python-socketio, websocket-client | `tests/api/requirements.txt` | `>=` floors | — | OK (unpinned floors) | consider a lock file |
| psycopg2-binary, tabulate | `testdata/harness/requirements.txt` | `>=` floors | — | OK (unpinned floors) | consider a lock file |
| fastapi | `services/document-service/pyproject.toml` | ^0.110.0 | 0.162.0 | Behind (caret on 0.x pins to 0.110.*) | `>=0.115,<1` |

## 4. Base images (Dockerfiles, `docker-compose*.yml`, deploy scripts)

| Component | File | Current | Latest stable | EOL status | Recommended |
|---|---|---|---|---|---|
| golang | `services/api-gateway/Dockerfile` | 1.22-alpine | 1.27.3 | **EOL** 2025-02-11 | `golang:1.27-alpine` (1.26 also supported) |
| alpine | `services/api-gateway/Dockerfile` | 3.19 | 3.24.3 | **EOL** 2025-11-01 | `alpine:3.24` |
| alpine | `demo-platform/runner/Dockerfile` | 3.20 | 3.24.3 | **EOL** 2026-04-01 | `alpine:3.24` |
| node | `demo-platform/dashboard`, `demo-platform/otter-projects`, `frontend/admin-dashboard`, `frontend/client-app`, `frontend/workbench`, `services/collab-service` Dockerfiles | 20-alpine | 26 | **EOL** 2026-04-30 | `node:24-alpine` |
| node (approved base) | `platform/standards/base-images.yaml` | 20-bookworm-slim@sha256 | 26 | **EOL** 2026-04-30 | add a node-24 entry (digest-pinned) |
| nginx-unprivileged | `frontend/admin-dashboard/Dockerfile` | 1.25-alpine | 1.30 stable / 1.31 mainline | **EOL** 2024-05-29 | `1.30-alpine` |
| nginx-unprivileged | `frontend/client-app/Dockerfile`, `frontend/workbench/Dockerfile` | 1.27-alpine | 1.30 / 1.31 | **EOL** 2025-06-24 | `1.30-alpine` |
| mcr dotnet sdk / aspnet | `services/audit-service/Dockerfile` (`aspnet:8.0-alpine` on `tech-partnerships`) | 8.0 | 10.0.13 (LTS) | **EOL < 90d** (2026-11-10) | `10.0`, plus `net10.0` TFM |
| eclipse-temurin JRE | auth-, notification-, analytics-service Dockerfiles | 17-jre-jammy | 25 LTS | OK (Temurin 17 to 2027-10-31; Ubuntu 22.04 standard support to 2027-06-01) | 21 or 25 `-noble` |
| gradle | auth-service, notification-service Dockerfiles + wrappers | 8.6-jdk17 | 9.8.2 (8.14.6) | Behind (8.x out of active support since 2025-07-31) | 8.14.x now, plan 9 |
| sbtscala/scala-sbt | `services/analytics-service/Dockerfile` | temurin-jammy-17.0.10_7_1.9.9_3.4.1 | sbt 1.13.1 / Scala 3.9 LTS | **EOL** (Scala 3.4 line, 2024-08-22) | Scala 3.9 LTS, sbt 1.13.x |
| ruby | `services/admin-service/Dockerfile` | 3.3-slim | 4.0.9 | OK (EOL 2027-03-31) | 3.4 |
| rust | `services/file-service/Dockerfile` | `latest` | 1.99.1 | Floating tag (not reproducible) | pin `rust:1.99-slim` |
| debian | file-service runtime | trixie-slim | 13 | OK (EOL 2030-06-30) | — |
| python | billing-, document-, search-, legacy-billing (+ `services/legacy-billing/bridge` on `tech-partnerships`) | 3.12-slim | 3.15.2 | OK (EOL 2028-10-31) | 3.13 when convenient |
| python | `migration/job/Dockerfile` | 3.12-slim-bookworm | 3.15 / trixie | OK (Debian 12 EOL 2028-06-30) | — |
| maven + temurin 8 | `services/report-service/Dockerfile` | 3.8.7-eclipse-temurin-8 / 8-jre | Maven 3.9.16 | **EOL** (Maven 3.8, 2025-06-14) | Legacy (by design) |
| maven + temurin 11 | `services/legacy-portal/Dockerfile` | 3.9-eclipse-temurin-11 / 11-jre-jammy | — | OK (Temurin 11 to 2027-10-31) | Legacy (by design) |
| postgres | `docker-compose.infra.yml`, `services/legacy-portal/docker-compose.onprem.yml`, `demo-platform/scripts/install-pgbouncer.sh`, analytics-service Testcontainers specs, `ci.yml:246` service (`postgres:15`) | 15-alpine / 15 | 18.6 | OK upstream (EOL 2027-11-11) but < 16 | `postgres:17-alpine` (match RDS, below) |
| postgres | `docker-compose.procs.yml`, `scripts/deploy-tenant.sh`, `scripts/lib/*-common.sh`, `demo-platform/reaper/reaper.sh`, `ci.yml:470` | 16 / 16-alpine | 18.6 | OK (EOL 2028-11-09) | — |
| redis | `docker-compose.infra.yml`, `scripts/deploy-tenant.sh`, `scripts/deploy-dev.sh` | 7-alpine | 8.10.3 | OK (7.4 EOL 2029-12-01) | — |
| localstack | `docker-compose.infra.yml` | 3.8 | 4.14.0 | Behind (1 major) | 4.x |
| meilisearch | `docker-compose.infra.yml` | v1.6 | v1.56.0 | **EOL** 2024-03-06 (only the latest minor is supported) | v1.56 (dump + reimport) |
| meilisearch | `scripts/deploy-tenant.sh` | v1.8 | v1.56.0 | **EOL** 2024-07-15 | v1.56 |
| prometheus | `docker-compose.infra.yml` | v2.51.0 | 3.15.1 | **EOL** 2024-04-30 | 3.13 LTS (EOL 2027-07-31) |
| grafana | `docker-compose.infra.yml` | 10.4.0 | 13.3.0 | **EOL** 2025-06-05 | 12.4 or 13.x |
| jaeger all-in-one | `docker-compose.infra.yml` | 1.55 | 2.22.0 | **EOL** (v1 line EOL 2025-12-31) | `jaegertracing/jaeger:2.x` |
| otel-collector-contrib | `docker-compose.infra.yml` | 0.96.0 | 0.164.0 | Behind (no LTS; only latest supported) | latest |
| fluent-bit | `docker-compose.infra.yml` | 3.0 | 5.1.5 | **EOL** 2024-10-08 | 5.1 |
| alertmanager | `docker-compose.incident.yml` | v0.28.1 | v0.34.2 | Behind | latest |
| oracle database free | `docker-compose.insurance.yml` (+ `docker-compose.oracle-billing.yml` on `tech-partnerships`) | `latest` | — | Floating tag | pin a release tag |
| alpine/k8s (kubectl) | `scripts/tenant-platform-baseline.sh` | 1.30.3 | 1.37.2 | **EOL** (k8s 1.30, 2025-07-15) | match the cluster (1.35+) |
| kubectl / helm / terraform (ARGs) | `demo-platform/runner/Dockerfile` | 1.30.4 / 3.15.4 / 1.9.5 | 1.37.2 / v4.3.1 / 1.17.1 | **EOL** (k8s 1.30; Terraform 1.9; Helm 3 security fixes end **2026-11-11**) | kubectl = cluster minor, Helm 4.x (or latest 3.x until 2026-11-11), Terraform 1.17 |
| external-dns | `demo-platform/k8s/dns-tls/external-dns.yaml` | v0.15.0 | v0.24.0 | Behind | latest |
| curl | `demo-platform/otter-projects/helm/.../values.yaml` | curlimages/curl:8.10.1 | — | Behind | latest |

### Managed services (Terraform), for completeness

| Component | File | Current | EOL status | Recommended |
|---|---|---|---|---|
| EKS | `platform/terraform/environments/dev.tfvars` | 1.34 | **EOL < 90d** (standard support ends 2026-12-02) | 1.35 / 1.36 |
| EKS (module default) | `platform/terraform/variables.tf` | 1.32 | **EOL** standard support 2026-03-23; extended (paid) to 2027-03-23 | 1.35+ |
| RDS PostgreSQL | `infrastructure/terraform/modules/database/main.tf` | 15.7 | OK (RDS 15 standard support to 2028-02-29); old minor | 17.x |
| Aurora PostgreSQL | `infrastructure/terraform/legacy-portal-serverless/variables.tf` | 16.13 | OK | — |
| ElastiCache Redis | `infrastructure/terraform/modules/cache/main.tf` | 7.1 | OK | — |

## 5. GitHub Actions (`.github/workflows/`)

No `actions/checkout@v2/@v3`, no `::set-output` / `::save-state` / `::set-env` / `::add-path`,
and no `setup-node` below Node 20. Many actions are SHA-pinned with a `# vX` comment; the
"Current" column uses that comment. The v4-era first-party majors run on the Node 20 action
runtime, which is EOL upstream; they still ran on GitHub-hosted runners in October 2026, so
they are reported as Behind, not broken.

| Component | File(s) | Current | Latest stable | EOL status | Recommended |
|---|---|---|---|---|---|
| actions/checkout | all 15 workflows (28 SHA-pinned, 18 tag) | v4 | v7.0.1 | Behind (3 majors) | v7 (SHA-pinned) |
| actions/setup-node | ci, client-e2e, procs-parity, workbench-pages | v4 | v7.1.0 | Behind | v7 |
| node-version | `ci.yml` lines 175, 306, 324, 343, 414; `client-e2e.yml`; `workbench-pages.yml` (+ `tp-golden-smoke.yml` x2 on `tech-partnerships`) | 20 | 26 | **EOL** 2026-04-30 | 24 |
| node-version | `procs-parity.yml` | 22 | 26 | OK (EOL 2027-04-30) | 24 |
| actions/setup-python | ci, equivalence-gate | v5 | v7.1.0 | Behind | v7 |
| actions/setup-java | ci, deps-remediation | v4 | v6.1.0 | Behind | v6 |
| actions/setup-go + go-version | `ci.yml`, `codeql.yml` | v5 / v5.6.0, Go 1.22 | v7.0.0, Go 1.27 | Go **EOL** | v7, Go from `go.mod` (`go-version-file`) |
| actions/setup-dotnet + dotnet-version | `ci.yml` | v4, 8.0.x | v6.0.0, 10.0 | .NET **EOL < 90d** | v6, 10.0.x |
| actions/upload-artifact | 9 uses, 8 workflows | v4 | v7.0.2 | Behind | v7 |
| actions/upload-pages-artifact / deploy-pages / configure-pages | `workbench-pages.yml` | v3 / v4 / v5 | v5 / v5 / v6 | Behind | latest |
| astral-sh/setup-uv | dast-scan, deps-remediation, equivalence-gate, procs-parity | v5 | v10.3.3 | Behind | v10 (SHA) |
| aws-actions/configure-aws-credentials | cd-tenant, docker-build, demo-reaper, platform-app-pipeline | v4 | v6.3.0 | Behind | v6 |
| aws-actions/amazon-ecr-login | cd-tenant, docker-build | v2 | v2.1.7 | OK | — |
| docker/build-push-action / setup-buildx-action | cd-tenant, docker-build | v5 / v3 | v7.4.0 / v4.4.1 | Behind | latest |
| azure/setup-helm / setup-kubectl | ci, demo-reaper, platform-standards | v4 / v4 | v5.0.1 / v5.2.0 | Behind | v5 |
| dorny/paths-filter | ci, cd-tenant | v3 | v4.0.3 | Behind | v4 |
| gradle/actions/setup-gradle | ci, deps-remediation | v3 and v4.4.4 | v6.4.1 | Behind (mixed majors) | one major, v6 |
| hashicorp/setup-terraform | ci, demo-reaper | v3 | v4.0.1 | Behind | v4 |
| helm/kind-action | `platform-app-pipeline.yml` | v1.10.0 | v1.15.1 | Behind (minor) | latest |
| github/codeql-action | `codeql.yml` | v4.38.2 | v4 (current major) | OK | — |
| SonarSource/sonarqube-scan-action | `sast-auto-remediate.yml` | v5 | v8.4.0 | Behind (3 majors) | v8 |
| ruby/setup-ruby, dtolnay/rust-toolchain | `ci.yml` | v1, stable | — | OK (floating) | — |
| java-version | `ci.yml` | 8, 11, 17 | 25 | 8/11 are Legacy (by design); 17 OK | — |
| python-version / ruby-version | `ci.yml`, `equivalence-gate.yml` | 3.12 / 3.3 | 3.15 / 4.0 | OK | — |

## 6. Go 1.22: complete pin list

`services/api-gateway/go.mod` declares `go 1.22` with no `toolchain` directive. Go 1.22 has
been EOL since **2025-02-11**; the supported releases are 1.26 and 1.27 (latest 1.27.3).
Every place that pins 1.22:

| File | Line | Pin | Branch |
|---|---|---|---|
| `services/api-gateway/go.mod` | 3 | `go 1.22` | main, tech-partnerships |
| `services/api-gateway/Dockerfile` | 1 | `FROM golang:1.22-alpine AS builder` | main, tech-partnerships |
| `.github/workflows/ci.yml` | 103 (main) / 92 (tp) | `go-version: '1.22'` | main, tech-partnerships |
| `.github/workflows/codeql.yml` | 57 | `go-version: '1.22'` | main (file absent on tech-partnerships) |
| `.github/workflows/tp-golden-smoke.yml` | 61 | `go-version: '1.22'` | tech-partnerships only |

No Makefile, script, Helm chart or Terraform file pins a Go version. The runtime stage is
`alpine:3.19` (EOL, §4). Recommended target: `go 1.26` in `go.mod` (keeps one supported
release of headroom) with `golang:1.27-alpine` / `alpine:3.24` and `go-version-file:
services/api-gateway/go.mod` in CI so the three pins cannot drift again.

## 7. Other runtime pins found (outside the requested files)

| Component | File | Current | Latest stable | EOL status | Recommended |
|---|---|---|---|---|---|
| Spring Boot | `services/auth-service/build.gradle` | 3.2.4 | 4.1.2 | **EOL** (OSS 2024-12-31; 3.5 also EOL 2026-06-30) | 4.0 (EOL 2026-12-31) or 4.1 (EOL 2027-07-31) |
| Spring Boot | `services/report-service/pom.xml` | 2.5.15 | 4.1.2 | **EOL** 2022-05-19 | Legacy (by design) |
| Spring Boot | `services/legacy-portal/pom.xml` | 2.7.18 | 4.1.2 | **EOL** (OSS 2023-06-30) | Legacy (by design) |
| Kotlin / Ktor | `services/notification-service/build.gradle.kts` | 1.9.23 / 2.3.9 | 2.4.21 / 3.x | Kotlin **EOL** 2024-05-21 | Kotlin 2.4, Ktor 3 |
| Scala / sbt | `services/analytics-service/build.sbt`, `project/build.properties` | 3.4.0 / 1.9.9 | 3.9 LTS / 1.13.1 | **EOL** (3.4) | 3.9 LTS, sbt 1.13 |
| Rails / Ruby | `services/admin-service/Gemfile(.lock)` | 7.1.6 / 3.3.11 | 8.1.4 / 4.0.9 | Rails **EOL** 2025-10-01 | Rails 8.1 (8.0 EOL 2026-11-07); keep the planted bug in `production.rb` |
| .NET TFM | `services/audit-service/*.csproj` | net8.0 | net10.0 | **EOL < 90d** (2026-11-10) | net10.0 |
| .NET Framework | `clients/windows-desktop/.../OtterWorks.Desktop.csproj` | 4.8 | 4.8.1 | Supported (follows Windows) | Legacy (by design) |
| Rust edition | `services/file-service/Cargo.toml` | 2021 | 2024 | OK | — |
