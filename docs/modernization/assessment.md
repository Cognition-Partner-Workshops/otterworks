# OtterWorks Modernization Estate Assessment

|   |   |
| --- | --- |
| Status | Draft for review. Documentation only, no code changes. Wave order updated with the programme owner's answer (§6). |
| Assessed on | 2026-10-07 |
| Branches | `main` @ `af476560`, `tech-partnerships` @ `32baffd8` (merge base `5d89a40c`; `tech-partnerships` is 600 commits ahead of and 210 behind `main`) |
| Scope | `main` (most of the platform) **plus two production estates that exist only on `tech-partnerships`**: the Oracle billing backend (`OW_BILLING`) and the CUSTBILL batch chain. Other TP-only content is noted but is not a modernization target (see §6). |
| Patterns | Each workload gets one pattern: **upgrade** (same stack, newer supported versions), **extract** (pull logic or data out of a monolith/database into its own service or store), **replatform** (move to a different runtime, host or library base with minimal logic change), **replace** (retire it, or rewrite it on a different stack) |

Support statuses are as of 2026-10-07. They come from upstream lifecycle policies (endoflife.date-style vendor schedules) and were **not** re-verified against live vendor pages during this assessment. Anything marked *verify* should be checked before it drives a contract or a deadline.

---

## 1. Sources

### 1.1 DeepWiki pages read

All pages of the DeepWiki for `Cognition-Partner-Workshops/otterworks` were retrieved (about 0.98 M characters). The pages below were read in detail and used for this assessment. The rest were skimmed for inventory only.

| Read in detail | Skimmed for inventory |
| --- | --- |
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
| --- | --- | --- |
| Gateway lives at `services/gateway/`, collab at `services/collaboration-service/` | DeepWiki overview | `services/api-gateway/`, `services/collab-service/` |
| File service is "Rust 1.77" | DeepWiki overview, System Architecture | `services/file-service/Dockerfile` builds from `rust:latest`. No toolchain pin, no `rust-toolchain.toml` |
| Web app is React/Next.js | DeepWiki page title, `ARCHITECTURE.md` (`frontend/web-app`) | `frontend/client-app` is React 18 + Vite 8. There is no Next.js in the product web app. Next.js is only used by the demo-platform dashboard and Otter Projects |
| procs demo legacy estate is "Oracle/PLSQL" | DeepWiki page 17 | On `main` it is PostgreSQL stored procedures emulating Oracle. A real Oracle backend exists only on `tech-partnerships` (`services/legacy-billing/db/oracle`, `docker-compose.oracle-billing.yml`) |
| "11 backend microservices" | DeepWiki overview | 10 core services plus report-service, legacy-portal (+3 Lambdas), legacy-billing, billing-service and the insurance Oracle fixture on `main`. `tech-partnerships` adds usage-bridge |
| Legacy ETL is Airflow/PySpark | Older guidance in DeepWiki 10.3 | Commit `87e96b5e` deliberately replaced the Airflow DAGs with cron scripts. Airflow is the target, not the current state |

### 1.3 Branch differences that change the estate

Rows marked **in scope** are production estates per the programme decision in §6.

| Area | `main` | `tech-partnerships` |
| --- | --- | --- |
| Legacy data migration (`migration/`: LDM job, Db2/Oracle archive charts, target SQL) | Present | **Absent** |
| `cloudworker/`, `incident/` harnesses | Present | Absent |
| `services/legacy-portal-lambda/` (3 Java 21 Lambdas) | Present | Absent |
| report-service / audit-service archive read path (Db2, SQL Server drivers) | Present | Removed |
| Legacy billing backend (**in scope**) | PostgreSQL stored procs only | PostgreSQL **or Oracle** (`db/oracle`, Oracle facade, `oracledb 2.5.1`). Production billing reads from Oracle |
| `services/legacy-billing/bridge` (usage-bridge, SQS → legacy billing) | Absent | Present |
| Gateway `/api/v1/billing` route | Absent | Present (`LegacyBillingURL`) |
| `etl/legacy-extra/` CUSTBILL chain (ksh, Bash/awk, Perl, Python Oracle extract) (**in scope**) | Absent | Present. Live: finance gets the CUSTBILL report every morning |
| `procs/oracle` parity tooling | Absent | Present |
| `mise.toml` toolchain pins, `tp-golden-smoke.yml` CI | Absent | Present |
| api-gateway Redis client (`go-redis/v9`) | Present | Absent |

---

## 2. Inventory

Columns: **Br** = branch presence (M = `main`, TP = `tech-partnerships`, both = both). **Supported?** = Yes / No / Partial, as of 2026-10-07.

### 2.1 Services

| Workload | Path | Br | Runtime | Framework & key versions | Supported? | Depends on |
| --- | --- | --- | --- | --- | --- | --- |
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
| Legacy Billing | `services/legacy-billing/app` | both (Oracle backend TP only) | Python 3.12 | Flask 3.1.1, Jinja, Gunicorn 23, psycopg 3.2.9. TP adds oracledb 2.5.1, `backends/oracle.py`, `facade.py`, and `reports.py` (RPT-114 month-end finance report served straight from Oracle) | **Yes** for the app layer. Business logic lives in stored procedures (`plans`, `rating`, `invoicing`, `dunning`) | PostgreSQL procs (M). PostgreSQL or Oracle `OW_BILLING` (TP, production) |
| Oracle billing estate (`OW_BILLING`) | `services/legacy-billing/db/oracle` | TP only (**in scope**) | Oracle Database (licensed in production; Oracle Free 23ai fixture in repo, `make oracle-billing-up`) | PL/SQL packages `pkg_ow_util`, `pkg_plans`, `pkg_rating`, `pkg_invoicing`, `pkg_dunning`. 155-column `CUSTOMER_MASTER` + `_HIST`, EAV `ENTITY_ATTR_VALUE`, bulk `INVOICE_HEADER`/`INVOICE_LINE` | **Licence renewal due next quarter. Programme decision: do not renew** | Read by legacy-billing (Oracle backend + finance report) and the CUSTBILL Oracle extract |
| Billing Service (extraction target) | `services/billing-service` | both | Python 3.12 | FastAPI <1, Uvicorn <1, Pydantic 2, psycopg 3 | **Yes** | Own `billing_svc` PostgreSQL schema |
| Usage Bridge | `services/legacy-billing/bridge` | TP only (part of the in-scope billing estate) | Python 3.12 | boto3 1.40.35, requests 2.32.5 | **Yes** | SQS usage events, legacy billing HTTP |
| Insurance commission pay | `services/industry-solutions/insurance` | both | Oracle Database Free 23ai (`database/free:latest`) | PL/SQL packages, OLTP + OLAP star schema, ETL package | **Partial.** Oracle Free is supported, but the image tag floats and Free is capped (2 CPU, 2 GB SGA, 12 GB data), so it is not a production target | Oracle only (fixture) |

### 2.2 Clients

| Workload | Path | Br | Runtime | Framework & key versions | Supported? | Depends on |
| --- | --- | --- | --- | --- | --- | --- |
| Web client (SPA) | `frontend/client-app` | both (23 files differ) | Node 20 build, nginx-unprivileged 1.27 (both branches) | React 18.2, Vite 8.1.4, TS 5.3, React Router 7.18, TanStack Query 5.28, TipTap 2.2, Zustand 4.5, Tailwind 3.4, Vitest 4, Playwright 1.59 | **Partial.** The libraries are current or maintained. The Node 20 build image is EOL. nginx 1.27 is a superseded mainline line | API Gateway (`/api/v1`), collab WebSocket |
| Mobile (Capacitor) | `frontend/client-app/mobile` | both | Capacitor 8.4.2 | Android minSdk 24 / target 36, AGP 8.13. iOS deployment target 15.0 | **Yes** | Same web bundle, gateway over HTTPS |
| Desktop (Electron) | `frontend/client-app/desktop` | both | Electron 43.1.0 (embedded Node) | electron-builder 26.15.3, TS 5.3 | **Likely yes.** Electron supports the latest 3 majors (*verify* the current major) | Same web bundle, embedded proxy to gateway |
| Admin Dashboard | `frontend/admin-dashboard` | both (23 files differ) | Node 20 build, nginx-unprivileged 1.25 | Angular 17.3, Angular Material 17.3, RxJS 7.8, TS 5.4, Karma 6.4 / Jasmine | **No.** Angular 17 LTS ended 2025-05-15. Karma is deprecated | API Gateway (admin, audit, analytics routes) |
| Windows Desktop | `clients/windows-desktop` | both | .NET Framework 4.8 | WPF/MVVM, classic non-SDK `.csproj`, `packages.config`, Newtonsoft.Json 13 | **Partial.** .NET Framework 4.8 is supported as a Windows component, but it is frozen. No tests in repo | API Gateway (auth, files, documents), DPAPI |
| Demo Platform Ops Dashboard | `demo-platform/dashboard` | both | Node 20 | Next.js 15.5 | **Partial.** Next 15 is the previous major. The Node 20 runtime is EOL | Kubernetes API, tenant namespaces |
| Otter Projects (ticketing demo) | `demo-platform/otter-projects` | both | Node 20 | Next.js 15.5 | **Partial** (same as above) | Its own DB, Devin API |

### 2.3 Batch jobs

| Workload | Path | Br | Runtime | Framework & key versions | Supported? | Depends on |
| --- | --- | --- | --- | --- | --- | --- |
| ETL `analytics_daily.py` (02:00 daily) | `etl/scripts` | both | Host `python3` (unpinned) via `/opt/etl/run.sh` on a single cron host | pandas 1.3.5, boto3 1.26.0, psycopg2-binary 2.9.3, requests 2.27.0 | **No.** The dependency set dates from 2021–22. pandas 1.3.5 has no wheels past Python 3.10, and the host Python is not pinned | SQS, DynamoDB, S3 data lake, PostgreSQL |
| ETL `storage_cleanup_daily.py` (02:30 daily) | `etl/scripts` | both | same | same | **No** | S3 file/quarantine buckets, DynamoDB metadata |
| ETL `audit_archive_weekly.py` (Sun 03:00) | `etl/scripts` | both | same | same | **No** | DynamoDB audit table, S3 archive |
| ETL `search_reindex_weekly.py` (Sun 04:00) | `etl/scripts` | both | same | same | **No** | document/file service APIs, MeiliSearch |
| ETL `user_activity_daily.py` (05:00 daily) | `etl/scripts` | both | same | same | **No** | PostgreSQL, S3 |
| CUSTBILL `sftp_ingest_poll.ksh` (*/15) | `etl/legacy-extra/jobs` | TP only (**in scope**) | ksh | none | **N/A.** Unowned script, no framework | SFTP drop, local filesystem |
| CUSTBILL `parse_custbill_fixedwidth.sh` (5-59/15) | `etl/legacy-extra/jobs` | TP only (**in scope**) | Bash, sed, awk, cut | none | **N/A** | Files from the ksh poller (no lock) |
| CUSTBILL `finance_excel_report.pl` (02:10 daily) | `etl/legacy-extra/jobs` | TP only (**in scope**) | Perl 5 (5.005-style, no modules) | None. It writes a CSV renamed to `.xls` and "emails" it through a sendmail pipe that silently no-ops | **N/A** | Parsed CUSTBILL `.psv` output. Overlaps `analytics_daily` at 02:00 |
| CUSTBILL `run_all.sh` (Sun 06:00) | `etl/legacy-extra` | TP only (**in scope**) | Bash | None. Stage dependency is `sleep 600`, and errors are discarded (`\|\| true`) | **N/A** | The three CUSTBILL jobs above. Input is the mainframe feed (job CB77340) dropped over SFTP, not Oracle |
| CUSTBILL month-end extract `tools/oracle_custbill_extract.py` (via `make tp-month-end`, not cron) | `etl/legacy-extra/tools` | TP only (**in scope**) | Python (`oracledb`) | None | **N/A** | Oracle `OW_BILLING` invoices, written as fixed-width CUSTBILL input for the parse + finance-report stages |
| Oracle `JOB_NIGHTLY_DUNNING` (DBMS_SCHEDULER, 02:00 daily) | `services/legacy-billing/db/oracle/schema/04_jobs.sql` | TP only (**in scope**) | Oracle DBMS_SCHEDULER | `pkg_dunning.sp_schedule_dunning` + `sp_suspend_overdue` | **Tied to the Oracle licence** | `OW_BILLING` |
| Oracle `JOB_PURGE_AUDIT_LOG` (DBMS_SCHEDULER, 03:30 daily) | same | TP only (**in scope**) | Oracle DBMS_SCHEDULER | 90-day `billing_audit_log` delete, `EXCEPTION WHEN OTHERS THEN NULL` | **Tied to the Oracle licence** | `OW_BILLING` |
| Analytics `usage-rollup` CronJob (`0 2 * * *`, `Forbid`) | `infrastructure/helm/analytics-service/templates/cronjob.yaml` | both | JVM 17 (analytics image) | `com.otterworks.analytics.batch.UsageRollupJob` (Scala 3.4 / Akka stack) | **No** (inherits analytics-service status) | Reads usage events (`usage-events.ndjson` / S3). Writes a JSON report to an `emptyDir` volume, so the output is discarded with the pod |
| LDM migration job | `migration/job` + `migration-job` chart | M only | Python 3.12 (`python:3.12-slim-bookworm`) | Pydantic 2, PyYAML 6, ibm_db 3.2 (optional), Spark local mode | **Yes** | Db2 / Oracle source, PostgreSQL / Azure SQL target |
| Demo reaper (`reaper-cronjob`) / tenant runner | `demo-platform/reaper`, `demo-platform/runner` | both | Bash on `alpine:3.20` (runner image) | kubectl, helm, terraform | **No.** Alpine 3.20 EOL Apr 2026 | EKS, Terraform state |
| Otter Projects poller | `demo-platform/otter-projects/helm/.../poller-cronjob.yaml` | both | Node 20 | Next.js app code | **No** (Node 20) | Otter Projects DB |

### 2.4 Data estates and platform dependencies

| Component | Version in repo | Br | Supported? |
| --- | --- | --- | --- |
| EKS | `1.32` (`platform/terraform/modules/eks`) | both | **Partial.** Standard support ended about Mar 2026. Extended support (paid) runs to about Mar 2027 (*verify*) |
| RDS PostgreSQL | 15.7 | both | **Yes** for the major (community EOL Nov 2027). The minor version is stale |
| Aurora Serverless v2 (legacy portal) | PostgreSQL 16.13 | M | Yes |
| ElastiCache Redis | 7.1 | both | Yes |
| MeiliSearch | v1.6 | both | **No.** Only the latest v1.x gets fixes |
| Db2 archive (`db2-archive` chart) | Db2 Community 11.5.9.0 | M only | Yes (*verify* IBM 11.5 end-of-support date) |
| Oracle archive (LDM source fixture) | `gvenzl/oracle-free:23-slim` (digest recommended but not pinned) | M | Partial (floating tag, Free-edition caps) |
| Oracle billing (`OW_BILLING`) | Production: licensed Oracle. Repo fixture: Oracle Database Free (`docker-compose.oracle-billing.yml`) | TP (**in scope**) | **Licence renewal due next quarter and will not be renewed.** This is the programme's hard deadline |
| Terraform / AWS provider | `>= 1.6`/`>= 1.7`, AWS `~> 5.40` / `~> 5.80`. TP pins Terraform 1.15.8 in `mise.toml` | both | Partial (AWS provider 6.x is current) |
| Lambda runtimes | `python3.12`, `java21` | both / M | Yes |
| Observability | Prometheus 2.51, Grafana 10.4, Jaeger all-in-one 1.55, OTel Collector 0.96 | both | **No.** Prometheus 2.51 and Grafana 10.4 are past support. Jaeger v1 reached EOL end of 2025 |

---

## 3. Pattern per workload

| Workload | Pattern | One-line reason |
| --- | --- | --- |
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
| Oracle billing estate `OW_BILLING` (TP) | extract | The licence is not being renewed. Move `rating`, `invoicing`, `dunning` logic into billing-service and the data into PostgreSQL, then switch Oracle off. |
| Oracle DBMS_SCHEDULER jobs (dunning, audit purge) (TP) | extract | They are business logic running inside Oracle. They become scheduled jobs owned by billing-service. |
| Insurance commission pay (Oracle) | extract | Commission logic is in PL/SQL packages. Same extract-to-service pattern as billing. |
| Web client (SPA) | upgrade | The libraries are current. Only the Node build image and nginx base are behind. |
| Mobile (Capacitor) | upgrade | Already on Capacitor 8 / SDK 36. Routine platform bumps. |
| Desktop (Electron) | upgrade | It must track Electron's 3-major support window. |
| Admin Dashboard | upgrade | Angular 17 is EOL. Stepwise `ng update` to a supported major is well-trodden. |
| Windows Desktop (WPF, net48) | replace | It duplicates the Electron client, has no tests, and sits on a frozen framework. Retire it in favour of Electron. |
| Demo Platform dashboard / Otter Projects / runner / reaper | upgrade | Node 20 and Alpine 3.20 are EOL. The app code is fine. |
| Legacy ETL (5 Python cron scripts) | replatform | Move the existing logic onto a managed orchestrator (Airflow/MWAA per `ETL_UPGRADE_GUIDE.md`) with retries, alerting and secrets. |
| CUSTBILL chain (ksh/Bash/Perl, TP) | replace | Four untested, unlocked, overlapping scripts in three languages feed a live daily finance report off Oracle. They are cheaper to rewrite as one orchestrated pipeline (per `ETL_UPGRADE_GUIDE_ADDENDUM.md`) than to port. |
| LDM migration job | upgrade | It is a supported tool whose purpose is to retire legacy stores. Keep it current until the Db2/Oracle archives are gone. |
| Db2 archive / Oracle archive data | extract | LDM moves proven rows to PostgreSQL / Azure SQL, then the legacy store is purged and retired. |

---

## 4. Risks

1. **The Oracle licence is a hard, near-term deadline.** The `OW_BILLING` licence renewal is due next quarter and will not be renewed. Billing reads, the RPT-114 month-end finance report (`reports.py`), the CUSTBILL month-end extract (`oracle_custbill_extract.py`, run through `make tp-month-end`) and two DBMS_SCHEDULER jobs all depend on Oracle today. The daily cron chain itself (`run_all.sh`) reads the mainframe SFTP feed, so which feed actually produces finance's morning report in production still has to be confirmed (§6). If the takeout slips past the renewal date, the options are an unplanned renewal or an outage of billing and finance reporting.
2. **The billing extraction is mostly not started.** billing-service implements only `plans` today (3 endpoints: list plans, entitlement, plan change). `rating`, `invoicing`, `dunning`, the nightly dunning job, the audit purge and the 155-column `CUSTOMER_MASTER` / EAV data model all still have to move. Invoicing and dunning only prove out over a full billing cycle, so a month-end has to fall inside the dual-run window, before the renewal date.
3. **Known anomalies must be carried over on purpose.** The finance report drops orphaned `INVOICE_LINE` rows "exactly as finance always ran it", and the seed manifests record exact known-anomaly counts. A clean-room rewrite that "fixes" these will fail reconciliation with finance. Each anomaly needs a keep-or-change decision recorded in the procs rule ledger.
4. **billing-service is not production-hardened.** Its README says the endpoints are "intentionally unauthenticated in this parity fixture". Making it the system of record means adding auth and tenant scoping before cutover, and that is behaviour the parity harness does not cover.
5. **Other hard support deadlines land in the same window.** .NET 8 (audit-service) ends 2026-11-10. Node 20 (collab, both frontend builds, demo platform) ended 2026-04-30. Go 1.22 (the internet-facing gateway) is out of support, and EKS 1.32 is on paid extended support. Spring Boot 3.2, Rails 7.1, Angular 17, Alpine 3.19/3.20 and Jaeger v1 are also past support.
6. **Wave 1 capacity.** Wave 1 now runs three tracks in parallel: the Oracle takeout (Python, PL/SQL, data migration), the CUSTBILL offload (ksh/Perl/Bash to a pipeline, with finance sign-off), and runtime upgrades (.NET, Node, Go, EKS). They need separate owners. Lower-urgency upgrades were moved to Wave 2 to make room (§5).
7. **Licence exposure beyond Oracle.** Akka 2.8 / Akka HTTP 10.5 (analytics, usage-rollup) are BSL 1.1. iText 5 (report-service) is AGPL. Legal should confirm both before Wave 2 scope is fixed.
8. **The two branches have to converge.** `main` runs most of the platform, but production billing and CUSTBILL live only on `tech-partnerships`, which is 600 commits ahead of `main` and 210 behind. Modernized billing and CUSTBILL code needs one home. Otherwise every fix has to be made twice and the branches drift further apart.
9. **The docs drift from the code** (§1.2). DeepWiki and `ARCHITECTURE.md` misstate paths, the web framework and toolchain versions, and DeepWiki calls the `main` billing estate Oracle when it is PostgreSQL.
10. **Golden-app policy conflicts with "fix everything".** `AGENTS.md` says `main` is the golden app with deliberately planted bugs, for example the Rails logging crash in `services/admin-service/config/environments/production.rb`. A framework upgrade can silently remove or change a planted failure. Every upgrade PR needs an explicit "planted behaviour preserved" check.
11. **Thin safety nets where the risk is highest.** Test-file counts on `main`: legacy-billing 0, windows-desktop 0, collab-service 3, auth-service 4, file-service 11 inline tests, audit-service 5. The CUSTBILL chain has no tests. The parity harnesses (procs record/replay including `procs/oracle` transcripts, the legacy-portal replay corpus, LDM reconciliation) are the real safety net.
12. **Credentials committed in the batch estate.** `etl/config.ini` holds AWS keys, a DB password and a MeiliSearch key as literals. The AWS keys look like AWS documentation example values, but the pattern is the problem, and the file's own header says the secrets-manager migration (ETL-142) was "deferred to Q3 2020".
13. **Batch fragility.** On the CUSTBILL side, schedules overlap with no locking, `run_all.sh` uses `sleep 600` as its dependency management and `|| true` to drop errors, the parser can read half-written files, and delivery goes through a sendmail pipe that silently no-ops. The finance recipient list is hardcoded and includes someone who left in 2020. The Python ETL has a single cron host, an unpinned host Python and swallowed exceptions.
14. **Unpinned build inputs.** `rust:latest` (file-service), `database/free:latest` (insurance) and the Oracle archive tag without a digest. A rebuild can change behaviour with no code change.
15. **Shared data couples upgrades.** In Compose, auth, document, admin and other services all point at one `otterworks` PostgreSQL database. Tenants share platform RDS/DynamoDB/S3 with logical isolation. Landing `billing_svc` on the same RDS instance adds load and blast radius there.

---

## 5. Waves

The order is set by the decision in §6. **Wave 1 covers everything with a hard external deadline: the Oracle licence, plus runtimes that are already out of support or about to lose it on internet-facing paths. The CUSTBILL offload goes in Wave 1 too, because the month-end extract reads from Oracle and the programme owner put it next to the takeout.** Wave 2 takes the remaining framework jumps and harness-backed extractions. Wave 3 is the rest of the data and batch estate.

### Wave 1: Oracle takeout, CUSTBILL offload, deadline runtimes

#### Track A: Oracle billing takeout (target: Oracle switched off before the renewal date)

- Extract `rating`, `invoicing` and `dunning` from `pkg_rating` / `pkg_invoicing` / `pkg_dunning` into billing-service, using the procs record/replay harness against both the PostgreSQL procs and the `procs/oracle` transcripts. Record every rule and known anomaly in the rule ledger.
- Move `JOB_NIGHTLY_DUNNING` and `JOB_PURGE_AUDIT_LOG` out of DBMS_SCHEDULER into scheduled jobs owned by billing-service. The purge must not keep the `WHEN OTHERS THEN NULL` silent failure.
- Migrate `OW_BILLING` data (`CUSTOMER_MASTER` + `_HIST`, `ENTITY_ATTR_VALUE`, invoices, audit log) to PostgreSQL. Reuse the LDM job's `oracle` → `postgresql` drivers and its reconcile/validate stages from `main`. LDM's existing copybooks and manifests describe only the document-retention archive tables, so budget for new `OW_BILLING` copybooks, field maps, record lengths and reconciliation rules (the 155-column `CUSTOMER_MASTER` and the EAV table are the bulk of that work).
- Re-point legacy-billing reads and the RPT-114 finance report to billing-service / PostgreSQL. Point usage-bridge at billing-service, or retire it.
- Add auth and tenant scoping to billing-service before it becomes the system of record.
- Dual-run Oracle and PostgreSQL through at least one month-end, cut over, then decommission Oracle.

#### Track B: CUSTBILL offload (target: the daily finance report no longer depends on Oracle or the cron host)

- Replace the ksh/Bash/Perl chain with one orchestrated pipeline (Databricks per `ETL_UPGRADE_GUIDE_ADDENDUM.md`, or the Wave 3 orchestrator if chosen first). It needs locking/`max_active_runs=1`, explicit stage dependencies, a real XLSX artifact and verified delivery to a managed distribution list.
- Replace the month-end Oracle extract (`oracle_custbill_extract.py` / `make tp-month-end`) with a PostgreSQL / billing-service source. This depends on the Track A data migration. Keep the mainframe CB77340 SFTP feed as an input unless the mainframe side is also being retired.
- Dual-run against the legacy chain until finance signs off, then remove `etl/legacy-extra/crontab`.

#### Track C: deadline runtime upgrades

- audit-service: .NET 8 → .NET 10 (first, because of the 2026-11-10 deadline)
- collab-service, client-app build, admin-dashboard build, demo-platform dashboard, Otter Projects: Node 20 → Node 22/24 LTS
- api-gateway: Go 1.22 → a supported Go, Alpine 3.19 → current
- EKS 1.32 → a version in standard support
- Hygiene: pin floating images, move `etl/config.ini` secrets to a secrets manager

#### Track D: branch convergence (enables A and B)

- Choose one home for the modernized billing-service, the legacy-billing Oracle facade and the CUSTBILL replacement, so Wave 1 work is not done twice across `main` and `tech-partnerships`.

**Measure Wave 1 worked:**

- *Oracle takeout:* procs parity at 100% golden-transcript match for `plans`, `rating`, `invoicing`, `dunning` against both PostgreSQL and Oracle transcripts
- *Oracle takeout:* data reconciliation, with per-table row counts and md5 checksums over ordered PK + amount (the seed-manifest contract) matching Oracle → PostgreSQL, and known-anomaly counts matching exactly or explained in the rule ledger
- *Oracle takeout:* financial reconciliation, with invoice totals by currency and status, dunning actions and suspensions identical between Oracle and billing-service for at least one full billing cycle including month-end
- *Oracle takeout:* sessions on `OW_BILLING` from any application or job at 0 for 14 consecutive days before the renewal date. Oracle instance decommissioned and licence not renewed
- *CUSTBILL:* finance report delivered by the current morning deadline on 100% of business days for 30 days, with delivery confirmed rather than assumed
- *CUSTBILL:* report totals by currency and record type matching the legacy chain on every dual-run day until finance signs off
- *CUSTBILL:* overlapping runs at 0, and entries in `etl/legacy-extra/crontab` at 0
- *Runtimes:* Track C workloads marked **No** or **Partial** in §2 because of an out-of-support runtime or base image at 0. Floating `:latest` / undigested image references at 0. Literal credentials in tracked config at 0
- *No regressions:* p95 latency and 5xx rate per upgraded service (Prometheus) within ±5% of the 7-day pre-change baseline. Critical/high image CVEs at or below baseline. SonarQube quality gate passing. Planted-bug and chaos scenarios on `main` still reproduce, and `tp-golden-smoke` still passes on TP

### Wave 2: Framework jumps and harness-backed extractions

- report-service: Java 8 / Boot 2.5 → Java 17/21 / Boot 3.x per `UPGRADE_GUIDE.md` (SpringFox → springdoc, iText 5 → OpenPDF, POI 5, commons-lang3)
- legacy-portal (`main` estate): cut traffic over to the three Lambdas, then retire the Boot 2.7 monolith. The Lambdas exist only on `main`. `tech-partnerships`' legacy-portal is outside the production scope set in §6, so it needs no cutover unless that scope changes
- auth-service: Spring Boot 3.2 → 3.5.x. admin-service: Rails 7.1 → 7.2 (planted-bug check per `AGENTS.md`). *Both moved here from Wave 1 to make room for the Oracle and CUSTBILL work. They are unsupported but have no external deadline.*
- notification-service: Kotlin 2 / Ktor 3
- analytics-service: Akka → Pekko, Scala 3.4 → 3.3 LTS or a current 3.x
- search-service: Flask → FastAPI per `TRANSLATION_GUIDE.md`
- admin-dashboard: Angular 17 → supported major, Karma → a supported runner
- document-service and file-service dependency bumps, Rust toolchain pin
- Observability (Jaeger v1 → v2, Prometheus/Grafana to supported lines), MeiliSearch to latest v1.x
- Characterization tests for collab-service and auth-service

**Measure Wave 2 worked:**

- legacy-portal replay corpus: 95/95 (or the full corpus) against the Lambda path, and monolith traffic share at 0% for 14 days before decommission
- report-service: generated CSV/PDF/XLSX outputs match the pre-upgrade baseline on a fixed fixture set
- search-service: API contract tests (`shared/openapi/search-service.yaml`) pass unchanged, with p95 search latency at or below baseline
- BSL/AGPL components in the production dependency tree: 0
- Workloads marked **No** in §2 for a runtime or framework reason: 0 across services and clients
- The same no-regression gates as Wave 1 (latency/5xx baseline, CVEs, SonarQube, planted-bug scenarios)

### Wave 3: Remaining data and batch estate

- Legacy ETL: replatform the 5 Python cron scripts onto the orchestrator chosen in Wave 1 Track B. Decommission the cron host
- `usage-rollup`: first persist the nightly batch report (it is written to an `emptyDir` today), so there is a baseline to compare against. Then replace the CronJob with event-driven processing
- LDM: run the Db2 (and Oracle archive) migrations to PostgreSQL / Azure SQL, then purge and retire the archives
- Insurance commission PL/SQL: extract the packages and migrate the commission OLTP/OLAP data. LDM does not cover this, because its Oracle overlay (`o27-*`) moves the document-retention tables only, so the data move needs its own mapping and reconciliation (a fixture today, not a production estate)
- Windows desktop: retire in favour of Electron after a usage check

**Measure Wave 3 worked:**

- Cron entries on the ETL host (`etl/crontab`): 0
- Batch success rate ≥ 99% over 30 days, every failure alerted (no silent `except: pass`), and every job safe to re-run (idempotency test)
- LDM reconciliation: row counts and hashes match for every migrated table, with rejects triaged to 0 unexplained before purge
- usage-rollup: daily aggregates from the event-driven path match the persisted batch reports for 14 consecutive days. Data freshness goes from up to 24 h to under 15 min
- Legacy stores (Db2 archive, Oracle archive, insurance Oracle) still serving reads: 0
- Active Windows desktop installs (telemetry or gateway user-agent): 0 before removal

---

## 6. Decision that sets the wave order

**Question asked (2026-10-07):** Which branch reflects production: `main`, `tech-partnerships`, or both?

**Answer from the programme owner:** Both. `main` is what most of the platform runs. The Oracle billing backend and the CUSTBILL batch chain on `tech-partnerships` are also live in production: finance gets the CUSTBILL report every morning, and billing still reads from Oracle. The Oracle licence renewal is due next quarter and will not be renewed, so the Oracle takeout and the CUSTBILL offload belong in Wave 1 next to the runtime upgrades, not in Wave 3. The inventory is `main` plus those two estates from `tech-partnerships`.

**What changed in this document as a result:**

- Scope (header, §1.3, §2) is `main` plus the TP Oracle billing estate (including usage-bridge and the two DBMS_SCHEDULER jobs, now inventoried) and the CUSTBILL chain. Other TP-only content (`mise.toml`, `tp-golden-smoke.yml`, `procs/oracle`, `docker-compose.tp.yml`) is treated as tooling. `procs/oracle` is used as a Wave 1 parity enabler.
- The Oracle takeout and the CUSTBILL offload moved from Wave 3 to Wave 1 (Tracks A and B), and a branch-convergence track (D) was added.
- auth-service (Spring Boot 3.2), admin-service (Rails 7.1), document/file dependency bumps, observability and MeiliSearch moved from Wave 1 to Wave 2 to keep Wave 1 deliverable.
- Risks 1–4, 6 and 8 were added or rewritten for the Oracle deadline.

**Still to confirm:**

- The exact Oracle renewal date. Every Wave 1 Track A milestone works back from it, and the dual-run must include a month-end before it.
- Which feed produces finance's morning CUSTBILL report in production. In the repo, the daily cron chain parses the mainframe CB77340 SFTP drop, and only the month-end path (`make tp-month-end`) extracts from Oracle. If the daily report is mainframe-fed, Track B's Oracle dependency is only the month-end run, and the daily offload can land after the takeout without blocking it.

---

## 7. Limitations

- Support statuses come from published lifecycle policies and were not re-checked live. Items marked *verify* need confirmation.
- No builds, tests or dependency scans were run for this assessment. Versions come from manifests, lockfiles and Dockerfiles on each branch.
- Test-file counts are a coverage proxy, not measured coverage.
- Licence conclusions (Akka BSL, iText AGPL, Oracle Free) are flags for legal review, not legal advice.
