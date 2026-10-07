# OtterWorks Modernization Estate Assessment

| | |
|---|---|
| Status | Draft for review. Documentation only, no code changes. |
| Assessed on | 2026-10-07 |
| Branches | `main` @ `af476560`, `tech-partnerships` @ `32baffd8` (merge base `5d89a40c`; `tech-partnerships` is 600 commits ahead of and 210 behind `main`) |
| Patterns | Each workload gets one pattern: **upgrade** (same stack, newer supported versions), **extract** (pull logic or data out of a monolith/database into its own service or store), **replatform** (move to a different runtime, host or library base with minimal logic change), **replace** (retire it, or rewrite it on a different stack) |

Support statuses are as of 2026-10-07. They come from upstream lifecycle policies (endoflife.date-style vendor schedules) and were **not** re-verified against live vendor pages during this assessment. Anything marked *verify* should be checked before it drives a contract or a deadline.

---

## 1. Sources

### 1.1 DeepWiki pages read

All pages of the DeepWiki for `Cognition-Partner-Workshops/otterworks` were retrieved (about 0.98 M characters). The pages below were read in detail and used for this assessment. The rest were skimmed for inventory only.

| Read in detail | Skimmed for inventory |
|---|---|
| 1 OtterWorks Overview, 1.2 System Architecture | 1.1 Getting Started |
| 2 Backend Services, 2.6 Search Service, 2.8 Analytics Service, 2.10 Audit Service, 2.11 Report Service & Legacy Portal | 2.1–2.5, 2.7, 2.9 (other service pages) |
| 3.1 Web App (React/Next.js), 3.2 Mobile & Desktop Clients, 3.3 Admin Dashboard (Angular) | 4.2 Helm Charts & Kubernetes, 4.3 Local Development with Docker Compose |
| 4.1 Terraform Infrastructure, 4.4 CI/CD Pipeline | 5 Multi-Tenant Demo Platform (+ 5.1, 5.2) |
| 10 ETL & Data Pipelines, 10.1 Legacy ETL Scripts, 10.2 Analytics Batch Jobs | 6 Observability (+ 6.1–6.3), 7 Security (+ 7.1, 7.2), 8 Chaos Engineering (+ 8.1, 8.2) |
| 16 Legacy Data Migration (LDM) | 9 Testing & Data (+ 9.1, 9.2), 11 Shared Contracts & Event Schemas, 12 Glossary |
| 17 Stored Procedures to Microservices (procs) | 13 Agent Skills & Workshop Playbooks, 14 DAST Security Harness, 15 Dependency CVE & Secure Refactor Harnesses |
| 19 Legacy Portal AWS Modernization Demos | 18 AWS Cloud Worker Demo, 20 Incident Responder Demo Harness |
| 21 Industry Solutions: Insurance Oracle Estate | 22 Otter Projects (Demo Ticketing App), 23 Cluster Scaling, Cost & DNS/TLS Operations |

### 1.2 Where DeepWiki and repo docs disagree with the code

The repository on each branch is the source of truth for the inventory. These mismatches matter because people will plan from the docs:

| Claim | Source | What the code says |
|---|---|---|
| Gateway lives at `services/gateway/`, collab at `services/collaboration-service/` | DeepWiki overview | `services/api-gateway/`, `services/collab-service/` |
| File service is "Rust 1.77" | DeepWiki overview, System Architecture | `services/file-service/Dockerfile` builds from `rust:latest`. No toolchain pin, no `rust-toolchain.toml` |
| Web app is React/Next.js | DeepWiki page title, `ARCHITECTURE.md` (`frontend/web-app`) | `frontend/client-app` is React 18 + Vite 8. There is no Next.js in the product web app. Next.js is only used by the demo-platform dashboard and Otter Projects |
| procs demo legacy estate is "Oracle/PLSQL" | DeepWiki page 17 | On `main` it is PostgreSQL stored procedures emulating Oracle. A real Oracle backend exists only on `tech-partnerships` (`services/legacy-billing/db/oracle`, `docker-compose.oracle-billing.yml`) |
| "11 backend microservices" | DeepWiki overview | 10 core services plus report-service, legacy-portal (+3 Lambdas), legacy-billing, billing-service and the insurance Oracle fixture on `main`. `tech-partnerships` adds usage-bridge |
| Legacy ETL is Airflow/PySpark | Older guidance in DeepWiki 10.3 | Commit `87e96b5e` deliberately replaced the Airflow DAGs with cron scripts. Airflow is the target, not the current state |

### 1.3 Branch differences that change the estate

| Area | `main` | `tech-partnerships` |
|---|---|---|
| Legacy data migration (`migration/`: LDM job, Db2/Oracle archive charts, target SQL) | Present | **Absent** |
| `cloudworker/`, `incident/` harnesses | Present | Absent |
| `services/legacy-portal-lambda/` (3 Java 21 Lambdas) | Present | Absent |
| report-service / audit-service archive read path (Db2, SQL Server drivers) | Present | Removed |
| Legacy billing backend | PostgreSQL stored procs only | PostgreSQL **or Oracle** (`db/oracle`, Oracle facade, `oracledb 2.5.1`) |
| `services/legacy-billing/bridge` (usage-bridge, SQS → legacy billing) | Absent | Present |
| Gateway `/api/v1/billing` route | Absent | Present (`LegacyBillingURL`) |
| `etl/legacy-extra/` CUSTBILL chain (ksh, Bash/awk, Perl, Python Oracle extract) | Absent | Present |
| `procs/oracle` parity tooling | Absent | Present |
| `mise.toml` toolchain pins, `tp-golden-smoke.yml` CI | Absent | Present |
| client-app nginx runtime | `nginx-unprivileged:1.25-alpine` | `nginx-unprivileged:1.27-alpine` |
| api-gateway Redis client (`go-redis/v9`) | Present | Absent |

---

## 2. Inventory

Columns: **Br** = branch presence (M = `main`, TP = `tech-partnerships`, both = both). **Supported?** = Yes / No / Partial, as of 2026-10-07.

### 2.1 Services

| Workload | Path | Br | Runtime | Framework & key versions | Supported? | Depends on |
|---|---|---|---|---|---|---|
| API Gateway | `services/api-gateway` | both | Go 1.22, `alpine:3.19` | Chi v5.0.12, golang-jwt v5.2.1, prometheus client 1.19.0, zerolog 1.32.0, go-redis v9.5.1 (M only) | **No.** Go 1.22 lost support Feb 2025. Alpine 3.19 EOL Nov 2025 | Every backend service URL, Redis (M), JWT secret shared with auth |
| Auth Service | `services/auth-service` | both | Java 17 (Temurin), Gradle 8.6 | Spring Boot 3.2.4, Spring Security 6, JJWT 0.12.5, Flyway 10.8.1 | **Partial.** Java 17 is supported. Spring Boot 3.2 OSS support ended Dec 2024 | PostgreSQL (shared `otterworks` DB), Redis |
| File Service | `services/file-service` | both | Rust edition 2021, `rust:latest` builder | Actix-Web 4, Tokio 1, aws-sdk-s3 1.15 / dynamodb 1.14 / sns 1.13, redis 0.25, opentelemetry 0.21 | **Partial.** The crates are maintained, but the toolchain is unpinned, so builds are not reproducible | S3, DynamoDB, SNS, Redis |
| Document Service | `services/document-service` | both (25 files differ) | Python 3.12 (`python:3.12-slim`) | FastAPI ^0.110, Uvicorn ^0.29, SQLAlchemy 2.0, asyncpg 0.29, Alembic 1.13, Pydantic 2.6, OTel 1.23 / 0.44b0 | **Partial.** Python 3.12 has security fixes to Oct 2028. FastAPI and OTel are pinned to early-2024 minors, and upstream patches only the latest | PostgreSQL, S3, SNS, Redis |
| Collaboration Service | `services/collab-service` | both | Node.js 20 (`node:20-alpine`) | TypeScript 5.4, Express 4.18.3, Socket.IO 4.7.4, Yjs 13.6.14, y-websocket 1.x, ioredis 5.3.2 | **No.** Node 20 EOL 2026-04-30. Express 4 is maintenance-only | Redis (pub/sub + adapter), auth JWT |
| Notification Service | `services/notification-service` | both | JVM 17, Gradle 8.6 | Kotlin 1.9.23, Ktor 2.3.9, AWS SDK for Kotlin 1.0.70 | **No.** Ktor 2.x was superseded by 3.x (Oct 2024). Kotlin 1.9 gets no fixes | SQS, SNS, SES, DynamoDB, WebSocket clients |
| Search Service | `services/search-service` | both | Python 3.12 | Flask 3.0.2, flask-restful 0.3.10 (no release since 2023), meilisearch 0.31.6, Gunicorn 22, boto3 1.34.69 | **Partial.** The runtime is supported. flask-restful is effectively unmaintained, and the Flask pin is behind 3.1 | MeiliSearch v1.6, SQS, Redis |
| Analytics Service | `services/analytics-service` | both | Scala 3.4.0 on JVM 17, sbt 1.9.9 | Akka HTTP 10.5.3, Akka 2.8.8 (Scala 2.13 artifacts via `for3Use2_13`), Circe 0.14.6 | **No / licence risk.** Scala 3.4 is a non-LTS line (3.3 is LTS). Akka ≥2.7 is under BSL 1.1 and needs a commercial licence for production above Lightbend's revenue threshold | SQS, S3 data lake, PostgreSQL |
| Admin Service | `services/admin-service` | both | Ruby 3.3 (`ruby:3.3-slim`) | Rails 7.1.6 (lock), Sidekiq 7.3.9, Puma 6.4, pg 1.5, jwt 2.8 | **Partial.** Ruby 3.3 is supported to Mar 2027. Rails 7.1 security support ended 2025-10-01 | PostgreSQL (shared `otterworks` DB in Compose), Redis (Sidekiq + chaos flags), Devin API |
| Audit Service | `services/audit-service` | both (archive path M only) | .NET 8 / ASP.NET Core 8 | Minimal API, AWSSDK 3.7.30x (DynamoDB, S3, SQS, SNS), Serilog 8.0.1, OTel 1.7, prometheus-net 8.2.1, Npgsql 8.0.5. M adds IBM Db2 8.0.0.400 and Microsoft.Data.SqlClient 5.2.2 | **Yes, until 2026-11-10** (.NET 8 LTS end, about 5 weeks away) | DynamoDB, S3, SQS/SNS. M: Db2 / PostgreSQL / Azure SQL archive store |
| Report Service | `services/report-service` | both (archive path M only) | Java 8 (Temurin 8), Maven | Spring Boot 2.5.15, SpringFox 3.0.0, Apache POI 4.1.2, iText 5.5.13.3, commons-lang 2.6, commons-io 2.6, Guava 28.0, `javax.*`. M adds Db2 JCC 11.5.9 and mssql-jdbc 12.6.1.jre8 | **No.** Spring Boot 2.5 OSS ended May 2022. SpringFox is dead. iText 5 is EOL and AGPL. The Java 8 runtime itself still gets Temurin updates | Analytics, audit and auth REST APIs, PostgreSQL. M: Db2 / SQL Server archive |
| Legacy Portal (monolith) | `services/legacy-portal` | both (parity fixtures differ) | Java 11, Maven | Spring Boot 2.7.18 (announcements, preferences, feedback modules) | **No.** Spring Boot 2.7 OSS ended Jun 2023. Java 11 still gets Temurin updates | PostgreSQL (3 schemas), EC2/ALB demo stack |
| Legacy Portal Lambdas ×3 | `services/legacy-portal-lambda/{announcements,preferences,feedback}` | M only | Java 21 (AWS Lambda `java21`) | aws-lambda-java-core / events, RDS Data API | **Yes** | Aurora Serverless v2 (Data API), API Gateway HTTP API, Terraform `legacy-portal-serverless` |
| Legacy Billing | `services/legacy-billing/app` | both (Oracle backend TP only) | Python 3.12 | Flask 3.1.1, Jinja, Gunicorn 23, psycopg 3.2.9. TP adds oracledb 2.5.1 | **Yes** for the app layer. Business logic lives in stored procedures (`plans`, `rating`, `invoicing`, `dunning`) | PostgreSQL procs (M), PostgreSQL or Oracle (TP) |
| Billing Service (extraction target) | `services/billing-service` | both | Python 3.12 | FastAPI <1, Uvicorn <1, Pydantic 2, psycopg 3 | **Yes** | Own `billing_svc` PostgreSQL schema |
| Usage Bridge | `services/legacy-billing/bridge` | TP only | Python 3.12 | boto3 1.40.35, requests 2.32.5 | **Yes** | SQS usage events, legacy billing HTTP |
| Insurance commission pay | `services/industry-solutions/insurance` | both | Oracle Database Free 23ai (`database/free:latest`) | PL/SQL packages, OLTP + OLAP star schema, ETL package | **Partial.** Oracle Free is supported, but the image tag floats and Free is capped (2 CPU, 2 GB SGA, 12 GB data), so it is not a production target | Oracle only (fixture) |

### 2.2 Clients

| Workload | Path | Br | Runtime | Framework & key versions | Supported? | Depends on |
|---|---|---|---|---|---|---|
| Web client (SPA) | `frontend/client-app` | both (23 files differ) | Node 20 build, nginx-unprivileged 1.25 (M) / 1.27 (TP) | React 18.2, Vite 8.1.4, TS 5.3, React Router 7.18, TanStack Query 5.28, TipTap 2.2, Zustand 4.5, Tailwind 3.4, Vitest 4, Playwright 1.59 | **Partial.** The libraries are current or maintained. The Node 20 build image is EOL. Both nginx branches (1.25, 1.27) are superseded mainline lines | API Gateway (`/api/v1`), collab WebSocket |
| Mobile (Capacitor) | `frontend/client-app/mobile` | both | Capacitor 8.4.2 | Android minSdk 24 / target 36, AGP 8.13. iOS deployment target 15.0 | **Yes** | Same web bundle, gateway over HTTPS |
| Desktop (Electron) | `frontend/client-app/desktop` | both | Electron 43.1.0 (embedded Node) | electron-builder 26.15.3, TS 5.3 | **Likely yes.** Electron supports the latest 3 majors (*verify* the current major) | Same web bundle, embedded proxy to gateway |
| Admin Dashboard | `frontend/admin-dashboard` | both (23 files differ) | Node 20 build, nginx-unprivileged 1.25 | Angular 17.3, Angular Material 17.3, RxJS 7.8, TS 5.4, Karma 6.4 / Jasmine | **No.** Angular 17 LTS ended 2025-05-15. Karma is deprecated | API Gateway (admin, audit, analytics routes) |
| Windows Desktop | `clients/windows-desktop` | both | .NET Framework 4.8 | WPF/MVVM, classic non-SDK `.csproj`, `packages.config`, Newtonsoft.Json 13 | **Partial.** .NET Framework 4.8 is supported as a Windows component, but it is frozen. No tests in repo | API Gateway (auth, files, documents), DPAPI |
| Demo Platform Ops Dashboard | `demo-platform/dashboard` | both | Node 20 | Next.js 15.5 | **Partial.** Next 15 is the previous major. The Node 20 runtime is EOL | Kubernetes API, tenant namespaces |
| Otter Projects (ticketing demo) | `demo-platform/otter-projects` | both | Node 20 | Next.js 15.5 | **Partial** (same as above) | Its own DB, Devin API |

### 2.3 Batch jobs

| Workload | Path | Br | Runtime | Framework & key versions | Supported? | Depends on |
|---|---|---|---|---|---|---|
| ETL `analytics_daily.py` (02:00 daily) | `etl/scripts` | both | Host `python3` (unpinned) via `/opt/etl/run.sh` on a single cron host | pandas 1.3.5, boto3 1.26.0, psycopg2-binary 2.9.3, requests 2.27.0 | **No.** The dependency set dates from 2021–22. pandas 1.3.5 has no wheels past Python 3.10, and the host Python is not pinned | SQS, DynamoDB, S3 data lake, PostgreSQL |
| ETL `storage_cleanup_daily.py` (02:30 daily) | `etl/scripts` | both | same | same | **No** | S3 file/quarantine buckets, DynamoDB metadata |
| ETL `audit_archive_weekly.py` (Sun 03:00) | `etl/scripts` | both | same | same | **No** | DynamoDB audit table, S3 archive |
| ETL `search_reindex_weekly.py` (Sun 04:00) | `etl/scripts` | both | same | same | **No** | document/file service APIs, MeiliSearch |
| ETL `user_activity_daily.py` (05:00 daily) | `etl/scripts` | both | same | same | **No** | PostgreSQL, S3 |
| CUSTBILL `sftp_ingest_poll.ksh` (*/15) | `etl/legacy-extra/jobs` | TP only | ksh | none | **N/A.** Unowned script, no framework | SFTP drop, local filesystem |
| CUSTBILL `parse_custbill_fixedwidth.sh` (5-59/15) | `etl/legacy-extra/jobs` | TP only | Bash, sed, awk, cut | none | **N/A** | Files from the ksh poller (no lock) |
| CUSTBILL `finance_excel_report.pl` (02:10 daily) | `etl/legacy-extra/jobs` | TP only | Perl 5 | CPAN Excel writer | **N/A** | Parsed CUSTBILL output, Oracle extract |
| CUSTBILL `run_all.sh` (Sun 06:00) + Oracle extract | `etl/legacy-extra` | TP only | Bash + Python (`oracledb`) | none | **N/A** | Oracle billing schema |
| Analytics `usage-rollup` CronJob (`0 2 * * *`, `Forbid`) | `infrastructure/helm/analytics-service/templates/cronjob.yaml` | both | JVM 17 (analytics image) | `com.otterworks.analytics.batch.UsageRollupJob` (Scala 3.4 / Akka stack) | **No** (inherits analytics-service status) | `usage-events.ndjson` / S3, PostgreSQL metrics tables |
| LDM migration job | `migration/job` + `migration-job` chart | M only | Python 3.12 (`python:3.12-slim-bookworm`) | Pydantic 2, PyYAML 6, ibm_db 3.2 (optional), Spark local mode | **Yes** | Db2 / Oracle source, PostgreSQL / Azure SQL target |
| Demo reaper (`reaper-cronjob`) / tenant runner | `demo-platform/reaper`, `demo-platform/runner` | both | Bash on `alpine:3.20` (runner image) | kubectl, helm, terraform | **No.** Alpine 3.20 EOL Apr 2026 | EKS, Terraform state |
| Otter Projects poller | `demo-platform/otter-projects/helm/.../poller-cronjob.yaml` | both | Node 20 | Next.js app code | **No** (Node 20) | Otter Projects DB |

### 2.4 Data estates and platform dependencies

| Component | Version in repo | Br | Supported? |
|---|---|---|---|
| EKS | `1.32` (`platform/terraform/modules/eks`) | both | **Partial.** Standard support ended about Mar 2026. Extended support (paid) runs to about Mar 2027 (*verify*) |
| RDS PostgreSQL | 15.7 | both | **Yes** for the major (community EOL Nov 2027). The minor version is stale |
| Aurora Serverless v2 (legacy portal) | PostgreSQL 16.13 | M | Yes |
| ElastiCache Redis | 7.1 | both | Yes |
| MeiliSearch | v1.6 | both | **No.** Only the latest v1.x gets fixes |
| Db2 archive (`db2-archive` chart) | Db2 Community 11.5.9.0 | M only | Yes (*verify* IBM 11.5 end-of-support date) |
| Oracle archive / Oracle billing | `gvenzl/oracle-free:23-slim` (digest recommended but not pinned), `database/free:latest` | M / TP | Partial (floating tags, Free-edition caps) |
| Terraform / AWS provider | `>= 1.6`/`>= 1.7`, AWS `~> 5.40` / `~> 5.80`. TP pins Terraform 1.15.8 in `mise.toml` | both | Partial (AWS provider 6.x is current) |
| Lambda runtimes | `python3.12`, `java21` | both / M | Yes |
| Observability | Prometheus 2.51, Grafana 10.4, Jaeger all-in-one 1.55, OTel Collector 0.96 | both | **No.** Prometheus 2.51 and Grafana 10.4 are past support. Jaeger v1 reached EOL end of 2025 |

---

## 3. Pattern per workload

| Workload | Pattern | One-line reason |
|---|---|---|
| API Gateway | upgrade | Go 1.22 and Alpine 3.19 are out of support. The code is small idiomatic Chi with no stack problem. |
| Auth Service | upgrade | Spring Boot 3.2 → 3.5.x stays inside the Jakarta/Boot 3 line with no API break. |
| File Service | upgrade | The stack is healthy. It needs a pinned toolchain and newer OTel/AWS crates, not a rewrite. |
| Document Service | upgrade | The runtime is current. Only 2024-era FastAPI and OTel pins need bumping. |
| Collaboration Service | upgrade | Node 20 is EOL. Moving to Node 22/24 LTS and Express 5 is a runtime bump, not a redesign. |
| Notification Service | upgrade | Kotlin 1.9 → 2.x and Ktor 2 → 3 are vendor-documented migrations on the same JVM. |
| Search Service | replace | Rewriting Flask/flask-restful onto FastAPI (`TRANSLATION_GUIDE.md` exists) drops an unmaintained library and puts both Python services on one stack. |
| Analytics Service | replatform | Swapping Akka (BSL) for Apache Pekko is a near drop-in library base change that removes the licence exposure. |
| Analytics `usage-rollup` CronJob | replace | `docs/BATCH-USAGE-ROLLUP.md` already targets event-driven EventBridge → SQS → Lambda instead of a nightly poll. |
| Admin Service | upgrade | Rails 7.1 is out of security support. 7.2/8.0 is the supported path on the same Ruby 3.3. |
| Audit Service | upgrade | .NET 8 support ends 2026-11-10. Retargeting to .NET 10 LTS is a framework bump. |
| Report Service | upgrade | `UPGRADE_GUIDE.md` already maps Java 8 → 17/21, Boot 2.5 → 3.x, `javax` → `jakarta`, SpringFox → springdoc and iText 5 → OpenPDF. |
| Legacy Portal (monolith) | extract | Three bounded contexts already have Lambda equivalents with a recorded parity corpus. Finish cutover and retire the monolith. |
| Legacy Portal Lambdas ×3 | upgrade | These are the target state on supported Java 21. Keep them current. |
| Legacy Billing | extract | Business rules live in stored procedures. Move them module by module into billing-service under the record/replay parity harness. |
| Billing Service | upgrade | This is the extraction target on a current stack. Extend it, keep dependencies current. |
| Usage Bridge (TP) | replace | It only exists to feed the legacy procs. Retire it once billing-service consumes usage events directly. |
| Insurance commission pay (Oracle) | extract | Commission logic is in PL/SQL packages. Same extract-to-service pattern as billing. |
| Web client (SPA) | upgrade | The libraries are current. Only the Node build image and nginx base are behind. |
| Mobile (Capacitor) | upgrade | Already on Capacitor 8 / SDK 36. Routine platform bumps. |
| Desktop (Electron) | upgrade | It must track Electron's 3-major support window. |
| Admin Dashboard | upgrade | Angular 17 is EOL. Stepwise `ng update` to a supported major is well-trodden. |
| Windows Desktop (WPF, net48) | replace | It duplicates the Electron client, has no tests, and sits on a frozen framework. Retire it in favour of Electron. |
| Demo Platform dashboard / Otter Projects / runner / reaper | upgrade | Node 20 and Alpine 3.20 are EOL. The app code is fine. |
| Legacy ETL (5 Python cron scripts) | replatform | Move the existing logic onto a managed orchestrator (Airflow/MWAA per `ETL_UPGRADE_GUIDE.md`) with retries, alerting and secrets. |
| CUSTBILL chain (ksh/Bash/Perl, TP) | replace | Four untested, unlocked, overlapping scripts in three languages are cheaper to rewrite as one pipeline (per `ETL_UPGRADE_GUIDE_ADDENDUM.md`) than to port. |
| LDM migration job | upgrade | It is a supported tool whose purpose is to retire legacy stores. Keep it current until the Db2/Oracle archives are gone. |
| Db2 archive / Oracle archive data | extract | LDM moves proven rows to PostgreSQL / Azure SQL, then the legacy store is purged and retired. |

---

## 4. Risks

1. **Hard support deadlines are already here.** .NET 8 (audit-service) ends 2026-11-10. Node 20 (collab, both frontends' builds, demo platform) ended 2026-04-30. Go 1.22, Spring Boot 3.2, Rails 7.1, Angular 17, Alpine 3.19/3.20 and Jaeger v1 are all past support. EKS 1.32 is on paid extended support.
2. **Licence exposure, not just support.** Akka 2.8 / Akka HTTP 10.5 (analytics, usage-rollup) are BSL 1.1. iText 5 (report-service) is AGPL. Oracle Database Free is capped and not a production target. Legal should confirm before Wave 2 scope is fixed.
3. **The two branches are two different estates.** `tech-partnerships` is 600 commits ahead of `main` and 210 behind. It drops LDM, the Lambdas and the archive read paths, and it adds an Oracle billing backend, usage-bridge and the CUSTBILL batch chain. A plan written against `main` alone misses the TP Oracle/batch estate, and vice versa.
4. **The docs drift from the code** (§1.2). DeepWiki and `ARCHITECTURE.md` misstate paths, the web framework and toolchain versions. Estimates built from docs will be wrong.
5. **Golden-app policy conflicts with "fix everything".** `AGENTS.md` says `main` is the golden app with deliberately planted bugs, for example the Rails logging crash in `services/admin-service/config/environments/production.rb`. A framework upgrade can silently remove or change a planted failure and break workshops that depend on it. Every upgrade PR needs an explicit "planted behaviour preserved" check.
6. **Thin safety nets where the risk is highest.** Test-file counts on `main`: legacy-billing 0, windows-desktop 0, collab-service 3, auth-service 4, file-service 11 inline tests, audit-service 5. The parity harnesses (procs record/replay, legacy-portal replay corpus, LDM reconciliation) are the real safety net, and they only cover billing plans, the portal and the archive slice.
7. **Business logic hidden in databases.** Billing rules sit in PostgreSQL procs (and Oracle on TP), and commission rules sit in Oracle PL/SQL. Only `plans` has been extracted so far. `rating`, `invoicing` and `dunning` remain.
8. **Credentials committed in the batch estate.** `etl/config.ini` holds AWS keys, a DB password and a MeiliSearch key as literals. The AWS keys look like AWS documentation example values, but the pattern is the problem, and the file's own header says the secrets-manager migration (ETL-142) was "deferred to Q3 2020".
9. **Batch fragility.** There is a single cron host, the host Python is unpinned, and exceptions are swallowed (`except: pass`). There is no idempotency or retry/alerting. On TP, CUSTBILL schedules overlap with no locking, so the parser can read half-written files.
10. **Unpinned build inputs.** `rust:latest` (file-service), `database/free:latest` (insurance) and the Oracle archive tag without a digest. A rebuild can change behaviour with no code change.
11. **Shared data couples upgrades.** In Compose, auth, document, admin and other services all point at one `otterworks` PostgreSQL database. Tenants share platform RDS/DynamoDB/S3 with logical isolation. Schema migrations in one service can break another tenant or service.
12. **Language spread.** Nine languages plus ksh, Perl and PL/SQL. Each wave needs reviewers for every stack it touches, and that, more than coding time, is the likely bottleneck.

---

## 5. Waves

The ordering principle is: **get every production path onto supported, pinned, reproducible foundations first. Then do the framework jumps and extractions that already have parity harnesses. Leave the data and batch estate, which has the weakest safety nets and the most stakeholders, for last.**

### Wave 1: Back to supported (runtime and platform bumps, no behaviour change)

- audit-service: .NET 8 → .NET 10 (first, because of the 2026-11-10 deadline)
- collab-service, client-app build, admin-dashboard build, demo-platform dashboard, Otter Projects: Node 20 → Node 22/24 LTS
- api-gateway: Go 1.22 → a supported Go, Alpine 3.19 → current
- auth-service: Spring Boot 3.2 → 3.5.x
- admin-service: Rails 7.1 → 7.2 (planted-bug check per `AGENTS.md`)
- document-service, file-service: dependency bumps, pin the Rust toolchain
- Platform: EKS 1.32 → a version in standard support, Jaeger v1 → v2, Prometheus/Grafana to supported lines, MeiliSearch to latest v1.x
- Hygiene: pin floating images (`rust:latest`, Oracle `:latest`), move `etl/config.ini` secrets to a secrets manager, add characterization tests to collab-service and auth-service

**Measure Wave 1 worked:**
- Wave 1 workloads marked **No** or **Partial** in §2 because of an out-of-support runtime, framework or base image: 0
- Floating `:latest` / undigested image references in Dockerfiles, compose files and charts: 0
- Critical/high CVEs in container images (Trivy / deps-remediation gate) at or below the pre-wave baseline. SonarQube quality gate passing on every touched service
- p95 latency and 5xx rate per upgraded service (Prometheus) within ±5% of the 7-day pre-upgrade baseline
- Planted-bug and chaos scenarios on `main` still reproduce (workshop smoke on `main`, `tp-golden-smoke` on TP)
- Literal credentials in tracked config files: 0

### Wave 2: Framework jumps and harness-backed extractions

- report-service: Java 8 / Boot 2.5 → Java 17/21 / Boot 3.x per `UPGRADE_GUIDE.md` (SpringFox → springdoc, iText 5 → OpenPDF, POI 5, commons-lang3)
- legacy-portal: cut traffic over to the three Lambdas, then retire the Boot 2.7 monolith
- legacy-billing → billing-service: extract `rating`, `invoicing`, `dunning` after `plans`
- notification-service: Kotlin 2 / Ktor 3
- analytics-service: Akka → Pekko, Scala 3.4 → 3.3 LTS or a current 3.x
- search-service: Flask → FastAPI per `TRANSLATION_GUIDE.md`
- admin-dashboard: Angular 17 → supported major, Karma → a supported runner

**Measure Wave 2 worked:**
- procs record/replay: 100% golden-transcript parity for each extracted billing module
- legacy-portal replay corpus: 95/95 (or the full corpus) against the Lambda path, and monolith traffic share at 0% for 14 days before decommission
- report-service: generated CSV/PDF/XLSX outputs match the pre-upgrade baseline on a fixed fixture set
- search-service: API contract tests (`shared/openapi/search-service.yaml`) pass unchanged, with p95 search latency at or below baseline
- Stored procedures still called by the legacy-billing HTTP layer: from 4 modules to 0
- BSL/AGPL components in the production dependency tree: 0

### Wave 3: Data and batch estate

- Legacy ETL: replatform the 5 cron scripts onto the orchestrator. Decommission the cron host
- `usage-rollup`: replace the CronJob with event-driven processing
- LDM: run the Db2 (and Oracle) archive migrations to PostgreSQL / Azure SQL, then purge and retire the archives
- TP: replace the CUSTBILL ksh/Bash/Perl chain. Extract the Oracle billing backend and insurance commission PL/SQL. Retire usage-bridge
- Windows desktop: retire in favour of Electron after a usage check

**Measure Wave 3 worked:**
- Cron entries on the ETL host (`etl/crontab`, `etl/legacy-extra/crontab`): 0
- Batch success rate ≥ 99% over 30 days, every failure alerted (no silent `except: pass`), and every job safe to re-run (idempotency test)
- LDM reconciliation: row counts and hashes match for every migrated table, with rejects triaged to 0 unexplained before purge
- usage-rollup: daily aggregates from the event-driven path match the batch output for 14 consecutive days. Data freshness goes from up to 24 h to under 15 min
- Legacy stores (Db2 archive, Oracle archive/billing, insurance Oracle) still serving reads: 0
- Active Windows desktop installs (telemetry or gateway user-agent): 0 before removal

---

## 6. Decision that sets the wave order

*Pending. The question will be put to the programme owner and the answer recorded here.*

---

## 7. Limitations

- Support statuses come from published lifecycle policies and were not re-checked live. Items marked *verify* need confirmation.
- No builds, tests or dependency scans were run for this assessment. Versions come from manifests, lockfiles and Dockerfiles on each branch.
- Test-file counts are a coverage proxy, not measured coverage.
- Licence conclusions (Akka BSL, iText AGPL, Oracle Free) are flags for legal review, not legal advice.
