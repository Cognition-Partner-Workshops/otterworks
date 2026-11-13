# OtterWorks threat model — demo-ciso (whole-platform security scan)

Scan target: `Cognition-Partner-Workshops/otterworks`, branch `demo-ciso` (user), pinned at `e65bd28db` (branch head at launch; 3 commits ahead of `main`). No security model file exists in the repo; this document builds on `ARCHITECTURE.md`, `AGENTS.md`, `security/dast/attack-surface.yaml`, and the earlier OtterWorks threat models (same component names, so findings line up across scans). Infrastructure is in the same repo (`infrastructure/`, `platform/terraform`); no separate infrastructure repository.

## User-stated priorities
- **Scope (user):** the whole repository — every language and service, Terraform, Kubernetes and Helm config, Dockerfiles, CI workflows, ignore lists (`.trivyignore`, `.gitleaksignore`, `security/dast/baseline.json`, etc.) and secrets. Not narrowed to one area.
- **Goal (user):** a real backlog to triage.
- **Main attack surface (user):** the public API (internet → ingress → `api-gateway` → backends) and the admin tools (`admin-service`, `frontend/admin-dashboard`, `/api/v1/admin`, `/api/v1/audit`, and the ops dashboard in `demo-platform/dashboard`).
- **Critical asset (user):** user files and documents — file blobs (S3), document content and metadata (Postgres), file metadata (DynamoDB), and the paths that reach them (documents, files/folders, search, shares/exports).
- **Out of scope / accepted risk (user):** nothing ruled out.

## What `demo-ciso` changes relative to `main`
- `infrastructure/terraform/modules/database/main.tf`: RDS `storage_encrypted = false` and `publicly_accessible = true`.
- `.trivyignore`: new Debian-slim CVE suppressions (some with `exp:` dates, `CVE-2024-6119` without), alongside the existing bulk `CVE-2021-*` ignore.
- `services/api-gateway/Dockerfile`: runtime base moved from `alpine:3.19` to `alpine:3.18.0`.
- `security/owners.yaml` + `security/owners.py`: service → owning team map (used for the `Owner` tag).

## System overview and trust boundaries
OtterWorks is a collaborative file storage and document editing platform (Drive + Docs equivalent): polyglot microservices (Go gateway, Java auth/report, Rust files, Python documents/search/billing, TS collab, Kotlin notifications, Scala analytics, Ruby admin, C# audit) and two frontends (Next.js web app, Angular admin dashboard) running on EKS cluster `otterworks-dev` behind a single shared ingress-nginx NLB. Each demo runs as a tenant namespace `otterworks-<id>`; `t-main` is the perpetual tenant tracking `main`.

Trust boundaries:
1. **Internet → ingress-nginx → `api-gateway`.** JWT (HS256, optional `PeerSecret`) validated in `services/api-gateway/internal/middleware/jwt.go`; public: `/api/v1/auth/login`, `/api/v1/auth/register`, `/health*`, `/metrics*`, `/socket.io*`. When `ProtectedPrefixPath` is set, unmatched prefixes skip validation. Routes in `internal/config/config.go` `ServiceRoutes()`.
2. **Gateway → backends.** Backends trust `X-User-ID` set by `internal/proxy/router.go`; per `attack-surface.yaml`, identity must come from validated claims, never from a client header, and backends are meant to be reachable only via the gateway.
3. **Services → data stores.** Shared RDS instance (per-tenant database `otterworks_<id>`), per-tenant Redis/MeiliSearch, shared S3 buckets and DynamoDB tables (Tier-A key/owner prefix isolation only), IRSA roles shared across `otterworks-*` via wildcard trust (`infrastructure/terraform/main.tf`).
4. **Tenant → tenant.** NetworkPolicy default-deny (`security/policies/`), ResourceQuota/LimitRange (`infrastructure/k8s/`); shared buckets/tables/IRSA are the weak point.
5. **Operators → control plane.** Ops dashboard (`demo-platform/dashboard`, passcode login in `app/api/auth/login/route.ts`) launches runner Jobs, reaper, tenant lifecycle against the cluster and AWS; `scripts/`, `incident/`, `cloudworker/`.
6. **CI/CD → cloud/cluster.** GitHub Actions (`.github/workflows/`, incl. `cd-tenant.yml` deploying `workshop-*`/`demo-*` pushes), GitHub OIDC role, ECR.

## Components
| Component | Code it covers |
|---|---|
| Edge & auth | `services/api-gateway`, `services/auth-service`, `frontend/`, `clients/` |
| Core services | `services/file-service`, `document-service`, `collab-service`, `search-service`, `notification-service`, `admin-service`, `billing-service`, `industry-solutions`, `legacy-portal*` |
| Analytics & reporting | `services/analytics-service`, `services/report-service`, `services/audit-service` |
| Data migration | `migration/`, `services/legacy-billing`, `procs/` |
| ETL batch | `etl/` |
| Demo control plane | `demo-platform/`, `scripts/`, `incident/`, `cloudworker/`, `demos/`, `.github/workflows/` |
| Infrastructure | `infrastructure/` (Terraform, Helm, k8s), `platform/terraform`, `security/policies`, `observability/` |
| Security tooling | `security/` (DAST, ingest, deps, equivalence), `compliance/`, `tests/`, `testdata/`, `shared/` |

## Entry points and who can reach them
- **Public (internet):** gateway `/api/v1/*` (login/register unauthenticated, rest bearer JWT), Socket.IO via collab-service, web and admin frontends, ops dashboard (passcode), legacy portal variants (`infrastructure/terraform/legacy-portal-*`).
- **Authenticated users:** documents, files/folders, search, notifications, collab rooms, shares/exports (`/api/v1/documents/exports`, `/api/v1/documents/shared`).
- **Admin role:** `/api/v1/admin`, `/api/v1/audit`, admin dashboard.
- **Internal only:** service-to-service HTTP, SQS/SNS consumers (disabled for tenants), Redis chaos flags read by the gateway (`internal/chaos`).
- **CI:** pushes/PRs to `main`, `workshop-*`, `demo-*`.

## Assets and data sensitivity
- **Critical (user):** user content — documents (Postgres), file blobs (S3) and metadata (DynamoDB), plus the search index and share tokens that expose them.
- Accounts and credentials: password hashes, MFA secrets, refresh tokens (auth-service), the gateway `JWT_SECRET`/peer secret, DB passwords, AWS/IRSA roles.
- Audit trail (audit-service, DynamoDB + S3 archive) — integrity for compliance.
- Tenant isolation and t-main (golden demo; a variant on t-main is treated as an incident per `AGENTS.md`).
- Control plane: dashboard IRSA role, GitHub OIDC role, ECR, `otterworks-demo-control` DynamoDB table.

## Attacker profiles
Nothing ruled out by the user; all apply, with the public API and admin tools as the primary surface:
- Unauthenticated internet attacker at the ingress/gateway.
- Authenticated user reaching other users' objects (IDOR, header spoofing, share-token forgery).
- A tenant/demo attendee reaching another tenant or shared AWS resources.
- Admin-role abuse / privilege escalation to admin.
- Malicious PR or compromised CI reaching repo/cloud secrets; anyone with repo read access (committed credentials).

## Existing controls
- Gateway JWT with public allowlist, rate limiting (`middleware/ratelimit.go`), CORS, circuit breaker.
- DAST expectations in `security/dast/attack-surface.yaml` with suppressed accepted findings in `security/dast/baseline.json`.
- Per-tenant namespace/DB/Redis/Meili; default-deny NetworkPolicy; ResourceQuota; reaper/idle-suspend.
- Trivy, CodeQL, SonarQube/SonarCloud, gitleaks (`.gitleaks.toml`, `.gitleaksignore`, `.trivyignore`, `security/scanning`).

## Out of scope / accepted risk
Nothing ruled out by the user. Note (`AGENTS.md`, not a user statement): the golden app contains **deliberately planted bugs** for bug-hunt labs (e.g. `services/admin-service/config/environments/production.rb`).

## Open questions
- Should planted lab bugs stay in the backlog or be treated as accepted risk? (Current reading: they stay — nothing ruled out.)
