# OtterWorks system brief (demo-bank)

Short, factual snapshot of the `demo-bank` branch. Refreshed by the weekly toil run on 2026-11-22.

## Services

| Service | Path | Stack |
|---------|------|-------|
| API Gateway | `services/api-gateway` | Go 1.22, chi v5 |
| Auth | `services/auth-service` | Java 17, Spring Boot 3.2.4 (Gradle) |
| File | `services/file-service` | Rust 2021, actix-web 4 |
| Document | `services/document-service` | Python 3.12, FastAPI 0.110 (Poetry) |
| Collaboration | `services/collab-service` | Node.js 20, Socket.io 4.8, Yjs 13.6 |
| Notification | `services/notification-service` | Kotlin 1.9.23, Ktor 2.3.9 (Gradle) |
| Search | `services/search-service` | Python 3.12, Flask 3.0 |
| Analytics | `services/analytics-service` | Scala 3, Akka HTTP 10.5 (sbt) |
| Admin | `services/admin-service` | Ruby 3.3, Rails 7.1 |
| Audit | `services/audit-service` | C# / .NET 8 |
| Billing | `services/billing-service` | Python 3.12, FastAPI (uv) |
| Report (legacy) | `services/report-service` | Java 8, Spring Boot 2.5.15 (Maven) |
| Legacy portal | `services/legacy-portal` | Java 8, Spring Boot 2.7.18 (Maven) |
| Legacy portal Lambdas | `services/legacy-portal-lambda/{announcements,feedback,preferences}` | Java 21, AWS SDK v2 (Maven) |
| Legacy billing | `services/legacy-billing` | Flask app + Oracle fixture |

## Front ends and tooling

- `frontend/client-app`: React 18 + Vite 8 SPA, Capacitor 8 mobile shells, Electron 43 desktop (`desktop/`).
- `frontend/admin-dashboard`: Angular 17.
- `frontend/workbench`: React 18 + Vite 8.
- `demo-platform/dashboard`, `demo-platform/otter-projects`: Next.js 15.5.
- Bank industry assets: `industries/banking/` (e.g. `vmware-wave-1/notify-svc`, Express 4.17).
- Other: `etl/`, `migration/job`, `tests/api` (end-to-end API suite), `clients/windows-desktop` (.NET Framework 4.8).

## Recent changes on demo-bank

- 2026-11-05: incident scenarios can be armed together with a batched storm (#2531); mock Slack Alertmanager channel (#2500); Sonar ingest with secure export transport (#2472); bank incident overlay and error-ratio zero fallback (#2477, #2486); bank synthetic docs (#2470); equivalence gate fix (#2496); `flake_rate.sh` hardening (#2476).
- 2026-10-23: `main` merged into demo-bank; bank wave 1 (#2154).
- 2026-11-22: weekly toil patch bumps (npm, Poetry, uv, Cargo, Maven, pip); `test_filter_by_title_fragment_in_a_busy_workspace` quarantined as flaky.

## Known issues

- `frontend/admin-dashboard` unit tests have 7 failures that reproduce on every run.
- `services/admin-service` production logger is a known planted bug on the golden app; leave it in place.
