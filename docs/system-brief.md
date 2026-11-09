# System brief

Branch snapshot: 2026-11-09. OtterWorks provides collaborative files, documents, and administration.
Versions below come from current manifests/locks; runtimes are declared targets or container images, not toil-run toolchains.

## Backend services

Paths are under `services/`. Each row gives the runtime, key framework/library versions, and purpose.

| Service | Language/runtime; key versions | Purpose |
|---|---|---|
| api-gateway | Go 1.22; Chi 5.0.14, JWT 5.2.3, go-redis 9.5.5 | Route requests, validate JWTs, rate-limit, and expose health/metrics. |
| auth-service | Java 17; Spring Boot 3.2.4, JJWT 0.12.5 | Registration, login, token management, and authorization. |
| file-service | Rust 2021 edition, `rust:latest` builder; Actix Web 4.13.0, Tokio 1.52.4 | Manage file metadata, uploads/downloads, folders, and object storage. |
| document-service | Python 3.12; FastAPI 0.110.3, SQLAlchemy 2.0.57, Pydantic 2.13.5 | Document CRUD, versions, templates, and sharing metadata. |
| collab-service | TypeScript/Node 20 image; Express 4.22.3, Socket.IO 4.8.4, Yjs 13.6.33 | Real-time collaborative editing and presence over WebSockets. |
| notification-service | Kotlin 1.9.23/JVM 17; Ktor 2.3.9 | Consume events and deliver notifications. |
| search-service | Python 3.12; Flask 3.0.3, MeiliSearch client 0.31.6 | Index and search document/file metadata. |
| analytics-service | Scala 3.4.3/JVM 17; Akka HTTP 10.5.3, Akka 2.8.8, Circe 0.14.17 | Collect usage metrics and serve analytics, reports, and exports. |
| admin-service | Ruby 3.3; Rails 7.1.6 | Administrative APIs for users, quotas, configuration, and audit data. |
| audit-service | C#/.NET 8; ASP.NET Core 8, Serilog.AspNetCore 8.0.1, Npgsql 8.0.5 | Record audit events and provide archive access. |
| billing-service | Python 3.12; FastAPI 0.141.1, Pydantic 2.13.5, psycopg 3.3.8 | Extracted subscription plans, entitlements, and plan-change APIs. |
| report-service | Java 8; Spring Boot 2.5.15, POI 4.1.2, iText 5.5.13.6 | Generate reports and expose legacy archive/reconciliation APIs. |
| legacy-billing | Python 3.12; Flask 3.1.1, psycopg 3.2.9 | HTTP facade for database-centric billing stored procedures. |
| legacy-portal | Java 11; Spring Boot 2.7.18 | Modular monolith for announcements, user preferences, and feedback. |
| legacy-portal-lambda/announcements | Java 21; Lambda core 1.2.3, AWS SDK 2.31.78, Jackson 2.18.12 | Announcements context extracted as Lambda handlers. |
| legacy-portal-lambda/preferences | Java 21; Lambda core 1.2.3, AWS SDK 2.31.78, Jackson 2.18.12 | User-preferences context extracted as Lambda handlers. |
| legacy-portal-lambda/feedback | Java 21; Lambda core 1.2.3, AWS SDK 2.25.70, Jackson 2.18.12 | Feedback context extracted as Lambda handlers. |

`services/industry-solutions/` contains solution documentation, not another deployable service.

## Other application surfaces

| Path | Language/runtime; key versions | Purpose |
|---|---|---|
| frontend/client-app | TypeScript/React 18.3.1, Vite 8.1.6; Node 20 build image | Browser client for files, documents, billing, and collaboration. |
| frontend/client-app/desktop | TypeScript/Electron 43.1.1, electron-builder 26.15.7 | Desktop shell with an embedded static/API proxy server. |
| frontend/admin-dashboard | TypeScript/Angular 17.3.12, Material 17.3.10; Node 20 build image | Administrative browser interface. |
| frontend/workbench | TypeScript/React 18.3.1, Vite 8.3.6; Node 20 build image | Workspace browser interface. |
| demo-platform/dashboard | TypeScript/Next.js 15.5.20, React 18.3.1; Node 20 image | Demo operations dashboard. |
| demo-platform/otter-projects | TypeScript/Next.js 15.5.29, React 18.3.1; Node 20 image | Project and automation webhook interface. |
| demo-platform/collection/mock-slack | JavaScript/Node 24 image, native HTTP server | Local collaboration and alert-channel surface. |
| clients/windows-desktop | C#/.NET Framework 4.8 WPF, Newtonsoft.Json 13.0.3 | Windows desktop client. |

Additional fixtures under `industries/banking/vmware-wave-1/`:
- `rates-batch`: Java 11, standalone batch application; calculate/export rates.
- `statements-web`: Java 8, Servlet API 3.1.0; serve statements through a WAR application.
- `kyc-docs`: Java 11, Spring Boot 2.3.12.RELEASE; store compliance documents.
- `branch-locator`: Python/Flask 1.1.4; locate branches.
- `notify-svc`: JavaScript/Node 12, Express 4.17.3, Redis client 3.1.2; notification templates and delivery API.

## Recent changes

From `git log origin/demo-bank`, 2026-10-26 through 2026-11-09:
- Added SonarQube ingestion/infrastructure-export tooling and tightened export transport/scanner scope (`eff8bdf12`, `35d2e8f13`).
- Added thread-bound multi-turn automation webhooks and preserved webhook isolation/optional reply reads (`4ce205a05`, `d65cf66c8`).
- Configured the mock Slack alert channel and expanded incident scenario arming (`22706b92a`, `ae25fcdbe`).
- Corrected incident error-ratio handling for absent 5xx series while traffic is positive (`a0d97a13f`).

This week's patch run (2026-11-09): 114 retained direct-dependency/tooling patch updates, 53 skipped candidates, and one flaky document-filter test quarantined; blocked/no-test modules were left unchanged.
