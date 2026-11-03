# OtterWorks security model

**Scope:** the whole `Cognition-Partner-Workshops/otterworks` repository, covering every service, both frontends, the demo platform, Terraform, Helm and CI.
This model is built from the code, `ARCHITECTURE.md`, `AGENTS.md` and `security/dast/attack-surface.yaml`, together with the security owner's priorities. Security scans use it to rank findings, so keep it current when trust boundaries change.

## Priorities (these drive the ranking)
OtterWorks is a **multi-tenant document platform**. The top concern is **one customer reaching another customer's files, documents or shares**. Priority order:
1. **Tenant / cross-customer isolation** of files (S3 + DynamoDB), documents (Postgres), share links, search results and collab rooms.
2. **Identity trust between services**: headers a client can set (`X-User-ID`, role headers), how each service validates the token, and admin routes that skip role checks.
3. **Secrets and default keys** in config: JWT secrets, `secret_key_base`, fallback secrets in code, and Helm/Terraform defaults.
4. **Path handling** on uploads and exports (traversal, archive paths, S3 key construction).
5. **Weak crypto on share links** (guessable or unkeyed tokens).
6. **SQL built from strings.**
7. **CORS.**
8. **Terraform and Helm** that expose any of the above (IRSA trust, bucket and table policies, NetworkPolicy, ingress).

**Ranking rule:** rank by what an **outside attacker** or a **signed-in customer** can actually reach **through the api-gateway**. A finding reachable only by an operator, a CI job, a local or dev-only setup, or code that is not served behind the gateway ranks below an equivalent gateway-reachable one.

## Components
| Name | Code | Notes |
|---|---|---|
| **client-app** | `frontend/client-app`, `frontend/admin-dashboard`, `frontend/workbench`, `clients/` | Customer SPA (React/Vite + Capacitor) and the Angular admin UI. Tokens live in `localStorage` (`src/lib/api-client.ts`). Search highlights render via `dangerouslySetInnerHTML` (`src/pages/search.tsx`). |
| **api-gateway** | `services/api-gateway` | Go/chi. The only internet-facing API. HS256 JWT check (`internal/middleware/jwt.go`). An optional `JWT_PEER_SECRET` also accepts a second deployment's tokens. Public routes: login, register, `/health*`, `/metrics*`, `/socket.io*`. On authenticated requests the proxy sets `X-User-ID` from `sub` (`internal/proxy/router.go`), but a client-supplied `X-User-ID` is **not stripped** on paths it does not overwrite. CORS has a credentialed allow-list (`internal/middleware/cors.go`). Routes `/api/v1/admin` go to admin-service. |
| **auth-service** | `services/auth-service` | Java/Spring Security. Users, BCrypt, MFA, JWT and refresh tokens (`JwtTokenProvider.java`). |
| **document-service** | `services/document-service` | FastAPI/Postgres. Re-decodes the JWT itself (`app/api/documents.py`) but **falls back to trusting `X-User-ID`** when no secret is set. Contains share links (`services/share_link.py`, unkeyed MD5 = planted OW-SEC-403), the export archive (OW-SEC-402 path traversal) and the filter repository (OW-SEC-401 SQL concatenation). |
| **file-service** | `services/file-service` | Rust/Actix. Owner comes from the `X-User-ID` header, **falling back to a multipart `owner_id` field** (`src/handlers.rs`). Blobs live in the shared S3 bucket and metadata in shared DynamoDB tables, so tenant isolation is a key-prefix/owner partition only. Also issues presigned URLs. |
| **backend-services** | `services/{collab,notification,search,analytics,admin,audit,billing,report}-service`, `services/legacy-*`, `services/industry-solutions` | collab-service JWT falls back to `'otterworks-dev-secret'` (`src/config.ts`). notification-service takes the user from `X-User-ID` **or a `user_id` query param** (`routes/Routes.kt`). search-service scopes by `X-User-ID`. admin-service (Rails) reads role from `request.env['jwt.user_role']`, with no visible base-controller role gate; chaos/alerts use shared-secret before_actions. `config/secrets.yml` has placeholder `secret_key_base` values for dev/test. |
| **infrastructure** | `infrastructure/terraform`, `infrastructure/helm`, `infrastructure/k8s`, `platform/`, `security/policies`, `.github/workflows` | IRSA roles trust `system:serviceaccount:<ns>:<svc>` **and** `<ns>-*` (every tenant namespace) via `StringLike` (`modules/irsa/main.tf`). Tenants share S3 buckets, DynamoDB tables and one RDS instance (DB per tenant). NetworkPolicies allow ingress from the ingress and monitoring namespaces. CI has deploy credentials. |
| **demo-platform** | `demo-platform/`, `scripts/`, `cloudworker/`, `incident/`, `migration/`, `procs/`, `etl/`, `security/{dast,deps,equivalence}`, `tests/`, `testdata/`, `demos/` | Tenant orchestration (dashboard, reaper, runner), operator scripts, migration jobs, lab harnesses and fixtures. Mostly operator-run or local. The ops dashboard is served separately from the product gateway. |

## Trust boundaries & entry points
1. **Internet → ingress-nginx (shared NLB) → api-gateway.** Anonymous callers reach the public routes. Everything else needs a JWT the gateway accepts. Some services are also exposed directly through their own Helm `ingress.yaml`; any such service bypasses the gateway's JWT check.
2. **api-gateway → backend services (ClusterIP).** The backends trust `X-User-ID`. Wherever the gateway forwards a client-set value, or a backend accepts a body or query identity instead, a signed-in customer can act as another customer.
3. **Tenant ↔ shared AWS.** Every tenant namespace runs under the same IRSA roles, against the same buckets and tables. Isolation depends on application-level prefixing.
4. **Operators / CI → cluster and AWS:** demo-platform, scripts and workflows. These are not reachable by customers through the gateway.

## Assets
- Customer files, documents, share links, exports, search index entries and collab state. **Cross-customer access is the top concern.**
- Credentials: gateway/peer JWT secrets, `secret_key_base`, DB passwords, refresh tokens, MFA secrets, IRSA permissions.

## Attacker profiles
- **Outside (anonymous) attacker** reaching the gateway or ingress.
- **Signed-in customer** attacking another customer's data, or escalating to admin.
- An insider, operator, CI or compromised dependency is not a named attacker. Findings reachable only this way rank below gateway-reachable ones.

## Existing controls
- Gateway JWT validation: HMAC-only algorithms plus an exp check.
- Per-IP rate limiting and a CORS allow-list.
- Owner checks in document-service (`_ensure_owner`).
- S3 public-access block and SSE, and RDS encryption.
- Per-tenant NetworkPolicy, ResourceQuota and LimitRange. SNS/SQS are disabled for tenants.

## Out of scope / accepted risk
- None stated.
- Planted lab bugs (`AGENTS.md`, `security/equivalence/findings.yaml`) are ranked on the same reachability rule as any other finding.

## Open questions
- Should workshop-attendee tenants (code-deploy rights in their own namespace) count as "customers" for tenant breakout through shared IRSA/S3? This model currently treats it as in scope, but below gateway-reachable cross-customer access.
- Is the demo-platform ops dashboard internet-exposed?
