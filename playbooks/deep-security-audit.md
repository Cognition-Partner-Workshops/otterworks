# Deep Security Audit Playbook

## Metadata

| Field | Value |
|---|---|
| **Title** | Deep Security Audit — Polyglot Microservice Codebases |
| **Description** | A systematic, multi-phase security audit that goes beyond single-service SAST. It maps cross-service trust boundaries, identifies auth inconsistencies across languages/frameworks, audits event-driven attack surfaces, and chains low-severity findings into composite high/critical vulnerabilities. |
| **Target Audience** | Devin sessions tasked with security review of any microservice-based repository |
| **Prerequisites** | Read access to all services, Dockerfiles, orchestration configs (docker-compose / k8s manifests), and any IaC (Terraform, Helm, etc.) in the target repository. Familiarity with common web frameworks (Spring, Flask, Express, Rails, Actix, etc.). |
| **Output Artifact** | `DEEP_SECURITY_AUDIT.md` in the repository root |
| **Estimated Duration** | 60–120 minutes depending on the number of services |

---

## Phase 1 — Reconnaissance & Attack Surface Mapping

### 1.1 Identify Services and Languages

Enumerate every backend service in the codebase. For each service, record:

| Service | Language / Framework | Port | Dockerfile? | Has Own Auth? |
|---------|---------------------|------|-------------|---------------|
| *(fill)* | | | | |

Sources to check:
- `docker-compose.yml`, `docker-compose.*.yml`
- Kubernetes manifests (`k8s/`, `helm/`, `infrastructure/`)
- Top-level `Makefile`, `README.md`, `ARCHITECTURE.md`
- `services/` or equivalent top-level directory listing

### 1.2 Map the Service Topology

Build a directed graph of service-to-service communication:

1. Parse `docker-compose.yml` or k8s manifests for `depends_on`, service links, environment variables referencing other service URLs (e.g., `AUTH_SERVICE_URL`, `SEARCH_SERVICE_URL`).
2. Identify the **API gateway** or edge proxy — the service that terminates external TLS and forwards requests.
3. Identify **message bus infrastructure** — SNS/SQS, Kafka, RabbitMQ, Redis pub/sub, NATS, etc.
4. For each service, determine: is it reachable **only** through the gateway, or also **directly** (e.g., exposed port in docker-compose with no network isolation)?

### 1.3 Enumerate Exposed Endpoints

For each service:
- List all HTTP routes (grep for route registration patterns: `@GetMapping`, `@app.route`, `router.Handle`, `#[get]`, `app.get(`, etc.)
- Classify each route: **public** (no auth), **authenticated** (requires JWT/session), **internal-only** (service-to-service)
- Flag any **unauthenticated sensitive endpoints**: alert ingestion, chaos/fault-injection, admin panels, debug/profiling endpoints, webhook receivers

### 1.4 Document the Trust Boundary Map

Create a table summarizing trust boundaries:

| Boundary | Mechanism | Notes |
|----------|-----------|-------|
| External → Gateway | JWT validation | |
| Gateway → Backend Service | Header injection (`X-User-ID`, etc.) | |
| Service → Service (sync) | Service token / mTLS / none? | |
| Service → Message Bus | IAM / shared credentials / none? | |
| Service → Database | Connection string in env / IAM auth? | |

---

## Phase 2 — Cross-Service Vulnerability Analysis

For each category below, systematically inspect every service and record findings.

### Category A — Trust Boundary Violations

Look for patterns where a downstream service **trusts an identity header without verifying it was set by an authenticated caller**:

1. **Header-trust fallback:** Search for code that reads identity from a header (e.g., `X-User-ID`, `X-Forwarded-User`, `X-Auth-User`) and uses it as the authenticated identity **without validating a JWT or session**. This is safe only if the service is guaranteed unreachable except through the gateway — check whether it is.
   - Search pattern: `request.headers.get("X-User-ID")`, `r.Header.Get("X-User-ID")`, `@RequestHeader("X-User-ID")`, etc.
   - Risk: If the service's port is exposed in docker-compose or k8s without a NetworkPolicy, an attacker can call it directly with a forged header.

2. **Direct backend access:** Check whether downstream service ports are mapped in `docker-compose.yml` (e.g., `ports: ["8082:8082"]`) or if k8s Services are of type `LoadBalancer`/`NodePort` instead of `ClusterIP`.

3. **JWT fallback to anonymous:** Search for code paths where JWT validation failure results in the request proceeding as an unauthenticated/anonymous user rather than being rejected (e.g., `if jwt_secret is None: pass`, `catch { /* ignore */ }`).

### Category B — Authorization Inconsistency

Compare the gateway's auth enforcement with each downstream service's own auth:

1. For the gateway: extract the list of routes and their auth requirements (which paths skip JWT validation? e.g., `/health`, `/metrics`, `/api/auth/*`).
2. For each backend service: extract its own auth middleware configuration.
   - Does the service re-validate the JWT, or does it only check for the presence of `X-User-ID`?
   - Are there endpoints that the service exposes without auth that the gateway also doesn't protect?
3. **CSRF audit:** For each service that disables CSRF protection, verify that compensating controls exist (e.g., stateless JWT auth with no cookie-based sessions, `SameSite` cookie attributes, custom header requirements).
   - Search: `csrf.disable()`, `csrf_exempt`, `protect_from_forgery skip:`, `#[disable(csrf)]`
   - If CSRF is disabled and the service uses cookie-based sessions, flag as **Medium**.
4. **Role/permission inconsistencies:** Check if one service enforces role-based access (e.g., `@PreAuthorize("hasRole('ADMIN')")`) while another service exposing similar data does not.

### Category C — Secrets & Credential Hygiene

1. **Hardcoded secrets in orchestration configs:**
   - Search `docker-compose.yml`, `.env.example`, `application.yml`, `config/secrets.yml`, `appsettings.json` for default passwords, API keys, JWT secrets.
   - Flag any secret with a guessable default value (e.g., `password: postgres`, `JWT_SECRET: change-me-in-production`, `SECRET_KEY: dev-secret`).
   - Check whether the same secret value is shared across multiple services (lateral movement risk).

2. **Suppression file audit:**
   - Read `.trivyignore`, `.snyk`, `.semgrepignore`, `.sonarcloud.properties` exclusions.
   - For each suppressed finding, assess: is it genuinely a false positive, or is it masking an exploitable vulnerability?
   - Flag any wildcard suppressions (e.g., `CVE-2021-*`) or bulk ignores without individual justification.
   - Check the age of suppressions — stale entries may mask vulnerabilities that now have exploits.

3. **Secrets in source code:** Search for hardcoded API keys, passwords, tokens, private keys in source files.
   - Patterns: `password\s*=\s*["']`, `api_key`, `secret_key`, `private_key`, `-----BEGIN`, `AKIA[A-Z0-9]{16}`

### Category D — Event-Driven Security

For each message bus consumer (SQS, SNS, Kafka, RabbitMQ, etc.):

1. **Schema validation:** Does the consumer validate the structure/schema of incoming messages before processing?
   - Search for JSON schema validation, deserialization with strict typing, or manual field checks.
   - If the consumer blindly deserializes and acts on message content, flag as **Medium** (event bus poisoning risk).

2. **Message authentication:** Is the message source verified? (e.g., SNS message signature validation, Kafka SASL, shared HMAC)
   - If any service can publish to the topic/queue without authentication, flag accordingly.

3. **Injection via message fields:** Do message field values flow into SQL queries, shell commands, file paths, or URLs without sanitization?

4. **Dead letter queue (DLQ) handling:** Are failed messages sent to a DLQ? Could a malicious message cause infinite retry loops or resource exhaustion?

### Category E — Infrastructure Misconfigurations

1. **Dockerfile audit** — for each service's Dockerfile:
   - Running as root? (missing `USER` directive or explicitly `USER root`)
   - Using `COPY . .` (recursive copy that may include `.env`, `.git`, test fixtures, secrets)?
   - Missing multi-stage build? (shipping compiler toolchains, dev dependencies in production image)
   - Pinned base image tags? (`FROM python:latest` vs `FROM python:3.12-slim`)
   - Health check present?

2. **IaC review** (Terraform, Helm, CloudFormation, Bicep):
   - Publicly accessible databases or storage buckets?
   - Overly permissive IAM roles/policies (e.g., `Action: "*"`, `Resource: "*"`)?
   - Missing encryption at rest or in transit?
   - Security groups with `0.0.0.0/0` ingress on sensitive ports?

3. **Network policies:**
   - In k8s: are NetworkPolicies defined? Is there a default-deny policy?
   - In docker-compose: are services on isolated networks, or all on the default bridge?

### Category F — Race Conditions & State Issues

1. **TOCTOU (Time-of-Check-to-Time-of-Use):**
   - File operations: check-then-open patterns (e.g., `if file.exists(): open(file)`)
   - Permission checks followed by action in separate steps without locking

2. **Concurrent token/credential rotation:**
   - If a service rotates JWT signing keys, database passwords, or API keys — is there a grace period for the old credential?
   - Can concurrent requests cause one request to use a stale key while another uses the new key?

3. **Distributed state consistency:**
   - Optimistic concurrency control: are there version/ETag checks on updates?
   - Shared mutable state in Redis/DynamoDB without proper locking (e.g., `WATCH`/`MULTI` in Redis)

4. **Rate limiting:**
   - Are there rate limits on authentication endpoints (login, token refresh)?
   - Are resource enumeration endpoints (list users, list documents) rate-limited?
   - Are resource IDs sequential/predictable (IDOR risk amplified without rate limiting)?

---

## Phase 3 — Vulnerability Chain Analysis

> **Purpose:** Individual findings — even Low and Medium severity — can combine into High or Critical composite vulnerabilities. After completing Phase 2, systematically attempt to chain findings together.

### 3.1 Chaining Methodology

For every Low and Medium finding from Phase 2:
1. List what **precondition** the finding provides to an attacker (e.g., "attacker learns internal schema", "attacker can reach service X directly", "attacker knows the JWT secret").
2. List what **capability** the finding grants (e.g., "forge identity headers", "publish arbitrary messages", "read any user's data").
3. Cross-reference preconditions and capabilities: does one finding's capability satisfy another finding's precondition?

### 3.2 Chain Patterns to Look For

| Chain Pattern | Individual Severities | Composite Severity | Example |
|---|---|---|---|
| **Info disclosure + Missing auth on internal endpoint → Unauthorized data access** | Low + Low | **High** | An exposed service port (docker-compose `ports` mapping) combined with a header-trust fallback (service trusts `X-User-ID` without JWT) allows an attacker to bypass the gateway entirely and access any user's data by setting a forged header. |
| **Weak default secret + Secret shared across services → Lateral movement** | Medium + Low | **Critical** | A guessable JWT secret (e.g., `change-me-in-production`) shared across all services via docker-compose means compromising or guessing a single secret grants the attacker the ability to forge valid JWTs accepted by every service. |
| **Verbose error messages + SQL injection in internal API → Data exfiltration** | Low + Medium | **High** | Detailed error responses reveal database schema (table names, column types), making SQL injection exploitation trivial — the attacker doesn't need to enumerate the schema blindly. |
| **No rate limiting + Predictable resource IDs → IDOR enumeration at scale** | Low + Medium | **High** | Sequential or predictable resource identifiers (e.g., auto-increment IDs) combined with no rate limiting allow an attacker to enumerate all resources by iterating IDs at high speed. |
| **Missing message schema validation + SSRF in file processor → Event bus poisoning to SSRF** | Low + Medium | **Critical** | An SQS/SNS consumer that doesn't validate message schema allows an attacker who can publish to the topic to inject a URL field that triggers SSRF in a downstream file processing service. |
| **CSRF disabled + No re-authentication for sensitive actions → Account takeover via CSRF** | Medium + Medium | **High** | With CSRF protection disabled and no re-authentication required for sensitive actions (password change, email change), an attacker can craft a cross-site request that modifies a victim's account when they visit a malicious page. |
| **Suppressed CVE + Exposed attack surface → Exploitable known vulnerability** | Low + Low | **Medium–Critical** | A `.trivyignore` entry suppressing a CVE with a known public exploit, combined with the vulnerable component being reachable from the internet (not just internal), creates an exploitable path. |
| **Permissive network policy + Service with elevated DB access → Privilege escalation** | Low + Medium | **High** | A service that has write access to shared database tables but no network isolation can be reached by a compromised lower-privilege service, escalating the attacker's database access. |

### 3.3 Documenting Chains

For each identified chain, document:

```markdown
### Chain [C-NNN]: [Title]

**Attack Chain:**
1. [Step 1 — leverage Finding F-XXX]: [description]
2. [Step 2 — leverage Finding F-YYY]: [description]
3. [Step 3 — achieve impact]: [description]

**Individual Findings:** F-XXX (Low), F-YYY (Medium)
**Composite Severity:** [High/Critical]
**Justification:** [Why the combination is worse than the sum of parts]
**Affected Services:** [list]
**Recommended Fix:** [What to fix to break the chain — often fixing one link is sufficient]
```

---

## Phase 4 — Triage & Report

Create `DEEP_SECURITY_AUDIT.md` in the repository root with the following sections:

### 4.1 Executive Summary

Two to three paragraphs summarizing:
- Number of services audited
- Total findings (by severity)
- Number of composite/chained vulnerabilities
- Top risks and recommended priority actions

### 4.2 Individual Findings Table

| ID | Category | Severity | Service(s) | File : Line | Description | Status | Recommended Fix |
|----|----------|----------|------------|-------------|-------------|--------|-----------------|
| F-001 | A (Trust Boundary) | Medium | *(service)* | `path/to/file:42` | *(description)* | Exploitable Now / Risk If Deployed | *(fix)* |
| ... | | | | | | | |

Severity levels: **Critical**, **High**, **Medium**, **Low**, **Informational**

Status classification:
- **Exploitable Now** — can be exploited in the current local-dev or deployed environment
- **Risk If Deployed** — only exploitable if current defaults/configs are used in production without override

### 4.3 Composite Vulnerability Table

| Chain ID | Finding IDs | Attack Chain Summary | Composite Severity | Justification |
|----------|-------------|---------------------|-------------------|---------------|
| C-001 | F-003 + F-007 | *(numbered steps)* | Critical | *(why the combination escalates)* |
| ... | | | | |

### 4.4 Suppression File Audit

| File | Suppressed ID | Justification Given | Assessment | Recommendation |
|------|--------------|-------------------|------------|----------------|
| `.trivyignore` | `CVE-XXXX-XXXXX` | *(from comments)* | Valid FP / Masking Real Risk / Stale | Keep / Remove / Investigate |

### 4.5 Cross-Reference with Existing SAST/SCA

If the repo has existing scan configurations (SonarCloud, Semgrep, Trivy, OWASP Dependency-Check, etc.):
- Note which of your findings are **already covered** by existing tooling
- Note which findings are **NOT detectable** by existing tooling (especially cross-service and chaining findings)
- Recommend additional tooling or rule additions if appropriate

---

## Phase 5 — Remediate Top Findings

Fix the **top 5 most critical findings** (prioritize composite/chained vulnerabilities and Critical/High individual findings):

1. For each fix:
   - Make the minimal code change required
   - Add a brief inline comment explaining the security rationale (only where the fix is non-obvious)
   - Run the service-specific tests to verify no regressions:
     ```
     # Adjust per service language — examples:
     # Go:     cd services/<svc> && go test ./...
     # Python: cd services/<svc> && pytest
     # Java:   cd services/<svc> && ./mvnw test
     # Rust:   cd services/<svc> && cargo test
     # Node:   cd services/<svc> && npm test
     # C#:     cd services/<svc> && dotnet test
     # Kotlin: cd services/<svc> && ./gradlew test
     # Ruby:   cd services/<svc> && bundle exec rspec
     ```
2. Run the service-specific linter to confirm no style regressions.
3. Update the `DEEP_SECURITY_AUDIT.md` findings table — set the status of remediated findings to **Remediated** and note the fix.

### Remediation Priority Order
1. Critical composite vulnerabilities (chains that yield Critical)
2. Critical individual findings
3. High composite vulnerabilities
4. High individual findings
5. Medium findings that are cheap to fix (e.g., removing a wildcard suppression, adding a `USER` directive to a Dockerfile)

---

## Phase 6 — Verify

### 6.1 Re-scan

Run available SAST/SCA tools to confirm no new findings were introduced by remediation:

```bash
# Examples — use whichever tools the repo has configured:
# Semgrep
semgrep scan --config auto .

# Trivy (filesystem scan)
trivy fs --severity HIGH,CRITICAL .

# Language-specific linters with security rules
# Go:     cd services/<svc> && go vet ./... && staticcheck ./...
# Python: cd services/<svc> && bandit -r app/
# Ruby:   cd services/<svc> && bundle exec brakeman
```

### 6.2 Update Report

In `DEEP_SECURITY_AUDIT.md`:
- Mark remediated findings with their new status
- Add a "Verification" section at the bottom confirming:
  - Which tools were re-run
  - That no new High/Critical findings were introduced
  - Any remaining findings that require follow-up (with owners/timelines if known)

### 6.3 Commit

- Stage only the remediation code changes and the `DEEP_SECURITY_AUDIT.md` report
- Do **not** commit temporary scripts, scan output files, or debug artifacts
- Use a conventional commit message: `fix(security): remediate top findings from deep security audit`
- Open a PR with the audit report and fixes for review
