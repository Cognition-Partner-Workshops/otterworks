# OtterWorks — System Brief

*One-page summary for executive / board review. Every claim links to the repo file it comes from; items marked **(inference)** are our reading, not a stated fact.*

## Purpose

OtterWorks is a collaborative file-storage and document-editing platform, "functionally equivalent to Google Drive + Google Docs" ([README.md](../README.md#L3), [ARCHITECTURE.md](../ARCHITECTURE.md#L3)). End users work in a web app; administrators use a separate admin dashboard ([README.md](../README.md#L65-L66)). The repo is also the base for workshops and demos: `main` is the "golden app", including deliberately planted bugs used in labs, and per-attendee copies run as separate tenants ([AGENTS.md](../AGENTS.md)).

## Architecture

- **11 backend microservices in 8+ languages:** Go API gateway, plus services in Java/Spring Boot, Rust/Actix, Python/FastAPI and Flask, Node.js/Socket.io, Kotlin/Ktor, Scala/Akka, Ruby/Rails and C#/ASP.NET ([README.md](../README.md#L43-L57), [services/](../services)).
- **Frontends:** React 18 web app, Angular 17 admin dashboard, and Capacitor mobile shells ([README.md](../README.md#L65-L67)).
- **Entry point:** the API gateway does routing, rate limiting and JWT validation ([README.md](../README.md#L47), [jwt.go](../services/api-gateway/internal/middleware/jwt.go)).
- **Deployment:** AWS EKS. Terraform is split into a platform layer ([platform/terraform](../platform/terraform)) and an app layer ([infrastructure/terraform/main.tf](../infrastructure/terraform/main.tf#L92-L157)). Each service has a Helm chart ([infrastructure/helm](../infrastructure/helm)). Shell scripts deploy the app ([scripts/deploy-dev.sh](../scripts/deploy-dev.sh)) and each tenant ([scripts/deploy-tenant.sh](../scripts/deploy-tenant.sh)). Docker Compose runs it locally ([docker-compose.yml](../docker-compose.yml)). CI/CD runs on GitHub Actions ([.github/workflows](../.github/workflows)).

## Data stores

| Store | Used for | Source |
|---|---|---|
| PostgreSQL 15 (RDS, `db.t3.small`) | Users, documents, admin data | [database/main.tf](../infrastructure/terraform/modules/database/main.tf#L53-L57), [main.tf](../infrastructure/terraform/main.tf#L99-L105) |
| Redis 7 (ElastiCache) | Sessions, collaboration state, rate limiting | [ARCHITECTURE.md](../ARCHITECTURE.md#L142-L150) |
| DynamoDB | File metadata, audit events, notifications | [database/main.tf](../infrastructure/terraform/modules/database/main.tf#L83-L84) |
| S3 | File content, analytics data lake | [ARCHITECTURE.md](../ARCHITECTURE.md#L142-L150) |
| MeiliSearch | Full-text search (master key kept in AWS Secrets Manager) | [docs/SDLC-COVERAGE.md](./SDLC-COVERAGE.md#L309) |

## Integrations

- **Inbound:** browser and mobile clients reach the API gateway through a single shared ingress-nginx load balancer, the only `LoadBalancer` Service allowed ([AGENTS.md](../AGENTS.md#L147)). CloudFront serves as the CDN ([ARCHITECTURE.md](../ARCHITECTURE.md#L150)).
- **Auth:** the gateway accepts HMAC-signed JWTs, with an optional second "peer" secret it falls back to ([jwt.go](../services/api-gateway/internal/middleware/jwt.go#L26-L27), [L75-L77](../services/api-gateway/internal/middleware/jwt.go#L75-L77), [L113](../services/api-gateway/internal/middleware/jwt.go#L113)). Terraform defines an AWS Cognito user pool with web and admin clients ([auth/main.tf](../infrastructure/terraform/modules/auth/main.tf#L13-L69)).
- **Outbound / events:** SQS/SNS carry domain events, and notifications go out by SES email, in-app push and webhooks ([ARCHITECTURE.md](../ARCHITECTURE.md#L90), [L152](../ARCHITECTURE.md#L152)). SNS/SQS is turned off for demo tenants ([AGENTS.md](../AGENTS.md#L66)).
- **AWS access:** each service gets its own IAM role through IRSA ([docs/SDLC-COVERAGE.md](./SDLC-COVERAGE.md#L307-L308)). App secrets (DB, JWT, Rails) are injected at deploy time ([docs/SDLC-COVERAGE.md](./SDLC-COVERAGE.md#L29)). Secret values are not reproduced here.

## Top 3 operational risks

**1. Shared single database instance for all data and all tenants — Severity: High**
All SQL-backed services and every demo tenant run on one RDS instance. Tenants are separated only by database name ([AGENTS.md](../AGENTS.md#L63)). Terraform sets no `multi_az`, and dev backups are kept for 1 day ([database/main.tf](../infrastructure/terraform/modules/database/main.tf#L53-L73)). Because `multi_az` is unset, the instance is likely single-AZ **(inference)**.
*Business impact:* if that one instance fails or is lost, every customer and every demo goes down at once, and recent data may not be recoverable.
*Mitigation:* turn on Multi-AZ, keep backups longer, and test a restore.

**2. Security controls are weaker than they look — Severity: High**
Kubernetes NetworkPolicies are defined but not enforced under default EKS VPC-CNI, which "give a false sense of enforcement" ([docs/SDLC-COVERAGE.md](./SDLC-COVERAGE.md#L109-L113)). Secrets are pushed in at deploy time rather than through External Secrets or Secrets Manager ([docs/SDLC-COVERAGE.md](./SDLC-COVERAGE.md#L29)). Trivy scans the source tree, not the built images ([security-scan.yml](../.github/workflows/security-scan.yml#L36), [docs/SDLC-COVERAGE.md](./SDLC-COVERAGE.md#L218-L220)). All JWTs are signed with shared symmetric secrets ([jwt.go](../services/api-gateway/internal/middleware/jwt.go#L75-L77)).
*Business impact:* one leaked secret or one compromised pod could reach other tenants' data. That is a breach and audit exposure.
*Mitigation:* enforce NetworkPolicies, move secrets to External Secrets Operator, and scan images in ECR.

**3. Stack sprawl, legacy components and an imperative release process — Severity: Medium**
Eleven services run on 8+ runtimes ([README.md](../README.md#L43-L57)). The report service is still on Java 8 / Spring Boot 2.5.15 ([pom.xml](../services/report-service/pom.xml#L12), [L25](../services/report-service/pom.xml#L25)), which is past open-source support **(inference)**. Releases run from shell scripts with no GitOps and no staging or prod promotion ([docs/SDLC-COVERAGE.md](./SDLC-COVERAGE.md#L114-L115)).
*Business impact:* staffing and patching cost more, unpatched CVEs pile up, and every release carries more risk.
*Mitigation:* fund the report-service upgrade, settle on fewer runtimes, and adopt GitOps with a staging environment.

*Note:* the admin-service crash-loop in [production.rb](../services/admin-service/config/environments/production.rb#L8) is a deliberate lab bug, not a production defect ([AGENTS.md](../AGENTS.md)).
