# System brief

OtterWorks is a polyglot collaborative file-storage and document-editing demo platform with tenant-management and legacy-modernization fixtures.

## Services and packages

Versions below are declarations on this branch, not a claim about deployed versions; ranges remain ranges.
Sources: each package's manifests and Dockerfiles (including banking `vm/Dockerfile`); iOS uses its Swift package manifest.
`services/`, `frontend/`, and `demo-platform/` prefixes are abbreviated as `svc/`, `ui/`, and `demo/`.

| Service/package | Language / framework | Key runtime or declared framework version |
|---|---|---|
| `svc/api-gateway` | Go / chi | Go 1.22; chi v5.0.12 |
| `svc/auth-service` | Java / Spring Boot | Java 17; Boot 3.2.4 |
| `svc/document-service` | Python / FastAPI | Python ^3.12; FastAPI ^0.110.3 |
| `svc/file-service` | Rust / Actix Web | Rust image `latest` (edition 2021); Actix Web 4 |
| `svc/search-service` | Python / Flask | Python 3.12; Flask 3.0.3 |
| `svc/collab-service` | TypeScript / Express, Socket.IO | Node 20 image; Express ^4.18.3; Socket.IO ^4.7.5 |
| `svc/notification-service` | Kotlin / Ktor | Java 17 image; Kotlin 1.9.23; Ktor 2.3.9 |
| `svc/analytics-service` | Scala / Akka HTTP | Java 17 image; Scala 3.4.0; Akka HTTP 10.5.3 |
| `svc/admin-service` | Ruby / Rails | Ruby ~>3.3.0; Rails ~>7.1.3 |
| `svc/audit-service` | C# / ASP.NET Core | .NET 8.0 (`net8.0`) |
| `svc/billing-service` | Python / FastAPI | Python >=3.12; FastAPI >=0.110.3,<1 |
| `svc/report-service` | Java / Spring Boot | Java 8; Boot 2.5.15 |
| `svc/legacy-portal` | Java / Spring Boot | Java 11; Boot 2.7.18 |
| `svc/legacy-portal-lambda/{announcements,preferences,feedback}` | Java / AWS Lambda | Java release 21 |
| `svc/legacy-billing/app` | Python / Flask | Python 3.12 image; Flask 3.1.1 |
| `svc/industry-solutions/insurance` | Oracle PL/SQL fixture | No application runtime manifest in this directory |
| `ui/workbench` | TypeScript / React, Vite | React ^18.2.0; Vite ^8.1.7; Node 20 build, nginx 1.27 serving |
| `ui/admin-dashboard` | TypeScript / Angular | Angular ^17.3.0; Node 20 build, nginx 1.25 serving |
| `ui/client-app` | TypeScript / React, Vite | React ^18.2.0; Vite ^8.1.7; Node 20 build, nginx 1.27 serving |
| `ui/client-app/desktop` | TypeScript / Electron | Electron 43.1.1 |
| `ui/client-app/mobile/android` | Capacitor / Android | JS Capacitor ^8.4.3; min SDK 24, compile/target SDK 36 |
| `ui/client-app/mobile/ios` | Swift / Capacitor | Swift tools 5.9; iOS >=15; native Capacitor package exactly 8.4.2 |
| `demo/dashboard` | TypeScript / Next.js, React | Node 20 image; Next 15.5.20; React 18.3.1 |
| `demo/otter-projects` | TypeScript / Next.js, React | Node 20 image; Next 15.5.29; React 18.3.1 |
| `demo/collection/mock-slack` | JavaScript / Node HTTP server | Node >=22 declared; Node 24 image |
| `demo/collection/mcp` | Grafana and PostgreSQL MCP adapters | Grafana MCP image 0.9.0; PostgreSQL MCP image 0.3.0 |
| `demo/runner`, `demo/reaper` | Bash / tenant operations | Alpine 3.20 runner; kubectl 1.30.4, Helm 3.15.4, Terraform 1.9.5 |
| `migration/job` | Python / `ldm` CLI, optional PySpark | Python >=3.12; PySpark >=3.5.9,<4 |
| `etl/` | Python / cron scripts, pandas | `python3` runner, no pinned interpreter; pandas 1.3.5 |
| `industries/banking/vmware-wave-1/branch-locator` | Python / Flask | Python 2.7.18 VM image; Flask 1.1.4 declared (compatibility not validated here) |
| `industries/banking/vmware-wave-1/rates-batch` | Java / batch JAR | Java 11 |
| `industries/banking/vmware-wave-1/statements-web` | Java / Servlet WAR | Java 8; Tomcat 8.5; Servlet API 3.1.0 |
| `industries/banking/vmware-wave-1/notify-svc` | JavaScript / Express, PM2 | Node 12.x; Express 4.17.3; PM2 4.5.6 in VM image |
| `industries/banking/vmware-wave-1/kyc-docs` | Java / Spring Boot | Java 11; Boot 2.3.12.RELEASE |
| `industries/banking/vmware-wave-1/fx-report` | Perl / CGI | Apache HTTP Server 2.4 image; system Perl version unpinned |

## Recent changes

Window: `git log origin/demo-bank --since='3 weeks ago' --first-parent`, read 2026-11-16; the returned entries are all dated 2026-11-05.

- Incident orchestration and alert delivery: concurrent arming of four scenarios and recoverable alert batches (#2531); mock Slack Alertmanager channel (#2500); absent-5xx-series fallback while traffic is positive (#2486).
- Incident workspace and bank rehearsal: shared workspace/MCP adapters (#2475), document-service alerts/dashboard overlay (#2477), and synthetic statement/KYC document seeds (#2470).
- Developer tooling and validation: SonarQube ingest export for Helm, Terraform and document-service (#2472); equivalence CI Python/Poetry setup (#2496); busy-workspace title-filter test and flake measurement script (#2476).
- This week's local maintenance: Python, Rust, report-service JVM and Node direct dependency patch bumps with lock updates; bumps for admin-dashboard, demo dashboard, legacy-billing, testdata harness and ETL were reverted because those modules lacked passing tests. Other JVM/Go/Ruby/.NET bumps remain deferred; no push.
