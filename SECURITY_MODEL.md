# OtterWorks threat model

Scan scope: `Cognition-Partner-Workshops/otterworks`, `main` (whole repository, as the "OtterWorks — demo-ciso" profile describes). The profile names the `demo-ciso` branch; this scan covers `main`, which lacks demo-ciso's 5 commits (report template preview, user-lookup initials, DB/endpoint settings, service ownership map). No `SECURITY_MODEL.md` exists. Infrastructure (Terraform, Helm, k8s) lives in the same repository, so no separate infrastructure repository was used.

**Provenance:** everything below is inferred from the code unless marked **(user)**.

## System overview and trust boundaries

OtterWorks is a collaborative file storage and document editing platform (like Drive plus Docs), built as polyglot microservices on EKS (`otterworks-dev`). It runs as multi-tenant demo tenants (one namespace each, `otterworks-<ID>`), plus the perpetual `t-main` tenant.

Trust boundaries:
1. **Internet → edge.** ingress-nginx (the single NLB) routes to `api-gateway` (`otterworks.workshop.example.com`), `web-app` and `admin-dashboard`. Every backend Helm chart also ships `ingress.enabled: true` with its own host (`<svc>.otterworks.workshop.example.com`, e.g. `infrastructure/helm/admin-service/values.yaml`). The per-service NetworkPolicy allows traffic from the ingress namespace, so where those hosts are deployed, backends are reachable without passing through the gateway.
2. **Gateway → services.** The gateway (`services/api-gateway/internal/middleware/jwt.go`) validates JWTs, except on public paths (`/api/v1/auth/login`, `/api/v1/auth/register`) and public prefixes (`/health`, `/metrics`, `/socket.io`). Services then enforce authorization themselves, with varying rigor.
3. **Tenant ↔ tenant.** Each tenant has its own namespace, Postgres database on the shared RDS instance, Redis and MeiliSearch. S3 buckets and DynamoDB tables are shared and isolated only by prefix or owner key (Tier A). IRSA roles are shared across `otterworks-*` through a wildcard trust.
4. **Cluster → AWS.** IRSA (`infrastructure/terraform/modules/irsa`) gives access to S3, DynamoDB, SQS/SNS and Cognito.
5. **CI/CD → cluster.** 16 GitHub workflows run under `.github/workflows`. `cd-tenant.yml` deploys any push to `workshop-*` or `demo-*` branches to that tenant.

## Components

| Component | Code |
|---|---|
| **Edge & Gateway** | `services/api-gateway`, `infrastructure/helm/ingress-nginx`, `infrastructure/helm/*/templates/ingress.yaml` |
| **Auth** | `services/auth-service` (Spring Security, JWT, BCrypt-12), `infrastructure/terraform/modules/auth` (Cognito) |
| **Content Services** | `services/file-service` (Rust, S3/DynamoDB), `services/document-service` (FastAPI), `services/collab-service` (Socket.io), `services/search-service`, `services/report-service`, `services/notification-service` |
| **Admin & Audit** | `services/admin-service` (Rails: users, chaos, feature flags, quotas, incidents), `services/audit-service` (C#), `services/analytics-service`, `frontend/admin-dashboard` |
| **Web Clients** | `frontend/client-app`, `frontend/workbench`, `clients/windows-desktop` |
| **Billing & Legacy** | `services/billing-service`, `services/legacy-billing`, `services/legacy-portal`, `services/legacy-portal-lambda`, `procs`, `etl`, `migration` |
| **Infrastructure & CI** | `infrastructure/terraform`, `platform/terraform`, `infrastructure/helm`, `infrastructure/k8s`, `.github/workflows`, Dockerfiles, `scripts`, `demo-platform` |

## Entry points and who can reach them

- `POST /api/v1/auth/register`, `POST /api/v1/auth/login` and `POST /api/v1/auth/refresh` are public. Self-registration means anyone on the internet can get a standard-user account (inferred from `SecurityConfig.java` and the gateway public paths).
- `/api/v1/{files,documents,search,audit,...}`: any authenticated user. Services must scope objects to the owner, as stated in `security/dast/attack-surface.yaml`.
- `/api/v1/auth/users/**` requires the ADMIN role. `/api/v1/auth/users/lookup` and `/by-id/**` accept any authenticated user.
- `/api/v1/admin/**` (admin-service) is meant to require JWT plus the admin role. The chaos and alert endpoints use shared-secret headers (`X-Chaos-Secret`) and **allow every request when the secret is unset** (`chaos_controller.rb#verify_chaos_secret`).
- `/socket.io` (collab) skips gateway JWT validation and must authenticate in the handshake.
- `/health` and `/metrics` are public through the gateway prefix list.
- Per-service ingress hosts (see boundary 1).

## Assets and sensitivity

- Users' files and documents, isolated per user and per tenant: **high**.
- Credentials, JWT signing secret (`JWT_SECRET`, with an in-code dev default in `auth-service/src/main/resources/application.yml`), Cognito, and service secrets in Helm `secret.yaml`: **critical**.
- AWS account and IRSA roles, shared buckets and tables, and the EKS cluster: **critical**.
- Admin control plane (users, suspend, feature flags, chaos): **high**.
- Billing and audit records: **medium/high**.

## Attacker profiles

1. An unauthenticated internet attacker at the edge.
2. A self-registered standard user (**(user)** anyone on the internet can sign up), attacking other users' objects (IDOR) or escalating to admin.
3. A user of one tenant reaching another tenant's data on the shared S3, DynamoDB, RDS or IRSA.
4. A supply-chain or CI attacker: workflow injection, a malicious branch push to `workshop-*`/`demo-*`, or a dependency CVE.
5. An insider or a compromised pod moving laterally inside the cluster.

## Existing controls

- Gateway JWT middleware, rate limiting, CORS and a circuit breaker.
- Spring Security role checks and BCrypt-12 password hashing.
- Per-tenant namespace, ResourceQuota, LimitRange and a cross-tenant-deny NetworkPolicy.
- A DAST harness with the attack-surface spec (`security/dast`, baseline is empty), Trivy config (`security/scanning`), the dependency advisory gate (`security/deps`) and SonarQube SAST (enterprise standard).
- Semgrep `nosemgrep` annotations mark deliberate exceptions (e.g. CSRF disabled for the stateless API).

## Out of scope / accepted risk

- **(user)** Nothing is ruled out: every attacker, asset and surface counts, legacy/demo code and local-only dev config included.
- Note from `AGENTS.md`: `main` deliberately contains planted bugs for labs (e.g. the admin-service `production.rb` logger crash). **(user)** They are not accepted risk, so findings on them keep their severity.

## Open questions

- Should the scan cover `demo-ciso` rather than `main`?
- Which assets matter most?
- Are the per-service ingress hosts actually deployed in tenants, or only the gateway?
