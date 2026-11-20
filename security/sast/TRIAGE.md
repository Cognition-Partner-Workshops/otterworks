# SonarQube findings triage (proposal)

Status: **proposal for owner approval** (Phase 0, Sprint 1: "run the approved SonarQube baseline
and agree how to handle findings"). Nothing here changes application code. The Phase 0 success
metric this supports is *no untriaged high/critical SonarQube findings*.

## 1. Principles

- **Baseline, then clean as you code.** The 84 findings in `baseline/issues.json` are the
  starting debt. The quality gate applies to *new* code only, so Phase 0 never blocks on
  pre-existing debt and never forces a behavior change.
- **Every Blocker/Critical gets a disposition**, not necessarily a fix. Fixes are scheduled
  into the epic that owns the service, behind that epic's parity tests.
- **Planted lab defects are preserved.** `main` is the golden demo app (see `AGENTS.md`).
  Findings that match a registered planted defect are marked, never fixed on `main`.
- **Coverage gaps are findings too.** A service with zero issues but no analyzer is reported as
  *not scanned*, not *clean*.

## 2. Dispositions

| Disposition | SonarQube action | Who decides | Required record |
|---|---|---|---|
| Fix | Leave open; link Jira issue | Service owner | Jira issue (label `sast`, `modernization`), target epic/sprint |
| Planted lab fixture | Accept, comment `planted: <ID>` | Security lead | Matching ID in `security/equivalence/findings.yaml`, `security/dast/attack-surface.yaml`, `scripts/bug-catalog.yaml` or `AGENTS.md` |
| Accepted risk | Accept, comment with expiry | Service owner + security lead | Reason, compensating control, review date (max 90 days) |
| False positive / safe | False positive (or hotspot Safe) | Security lead | One-line technical justification |
| Needs info | Leave open, assign owner | Triage rotation | Question, due within triage SLA |

## 3. Triage SLA and flow

| Severity (legacy) | Triage within | Fix target if "Fix" |
|---|---|---|
| Blocker | 2 business days | Next sprint of the owning epic, or accepted-risk record |
| Critical | 5 business days | Within the owning epic's current phase |
| Major | 1 sprint | Backlog, prioritized by owner |
| Minor / Info / code smells | No SLA | Opportunistic, when the file is touched |

1. Scan runs (`make sast-baseline` locally today; CI once a shared SonarQube server exists).
2. Weekly 30-minute triage: security lead + rotating service owner walk new Blocker/Critical
   issues and all security hotspots, set a disposition, and file Jira issues for "Fix".
3. Proposed quality gate on new code: 0 new Blocker/Critical vulnerabilities, all new security
   hotspots reviewed, 0 new Blocker/Critical bugs. Reported (not blocking) during Phase 0;
   enforced from the Phase 0 go/no-go onward if owners agree.
4. Phase 0 exit check: every Blocker/Critical in the baseline has a disposition.

## 4. Proposed initial triage of baseline Blocker/Critical findings

Proposed dispositions for owners to confirm; nothing has been marked in SonarQube yet.

| # | Severity | Rule | Location | Proposed disposition | Notes |
|---|---|---|---|---|---|
| 1 | Blocker vuln | typescript:S6418 | `frontend/admin-dashboard/src/app/core/services/auth.service.ts:102` | Fix (confirm with Admin owner) | Committed admin-role JWT in the offline mock login, which `login()` falls back to on any gateway error. Phase 0 Admin hardening candidate. |
| 2 | Blocker vuln | secrets:S6698 | `services/document-service/app/config.py:12` | Fix | Default DSN with dev password; same class as the ETL/Collab credential defaults in Sprint 3. Propose adding Document to that story. |
| 3 | Critical vuln | python:S4790 | `services/document-service/app/services/share_link.py:31` | Planted lab fixture | OW-SEC-403 (`security/equivalence/findings.yaml`). Do not fix on `main`. |
| 4 | Critical vuln | python:S4502 | `services/search-service/app/main.py:58` | Needs info, likely safe | Flask API without CSRF protection; safe only if no cookie-based auth reaches it. Search owner to confirm. |
| 5 | Critical vuln | docker:S6470 | `services/admin-service/Dockerfile:12` | Fix (low effort) | `COPY . .` with no `.dockerignore`. |
| 6 | Critical vuln | docker:S6470 | `services/search-service/Dockerfile:7` | Fix (low effort) | `COPY . .` with no `.dockerignore`. |
| 7 | Critical vuln | docker:S6470 | `services/document-service/Dockerfile:12` | Needs info, likely safe | `.dockerignore` present; confirm it excludes env/secret files. |
| 8-10 | Critical bug | typescript:S2871 | `admin-dashboard/.../migration.component.ts:406,407`, `client-app/src/pages/margins.tsx:84` | Needs info | Default `sort()` ordering; check whether client-app `margins.tsx` is part of a planted margin lab before any fix. |

No HIGH-probability security hotspots were returned.

## 5. Coverage gaps (decision needed)

The pinned SonarQube Community Build did **not** semantically analyze:

- `audit-service` (C#): needs SonarScanner for .NET and a build.
- `file-service` (Rust), `admin-service` (Ruby), `analytics-service` (Scala): no analyzer ran.
- Kotlin (`notification-service`) analysis completed but logged analyzer errors; treat as degraded.

Community Build also raised **no** finding on the registered injection and path-traversal lab
defects (OW-SEC-401 SQL injection, OW-SEC-402 path traversal) or the file-service client-supplied
identity header. Those need taint analysis, which SonarQube offers only in commercial
editions and SonarQube Cloud. Options:

1. Keep Community Build and cover the gaps with the existing Semgrep/Trivy jobs (no cost, weaker
   SonarQube evidence).
2. Use the existing SonarCloud project (`sonar-project.properties`) for taint analysis and the
   .NET scanner (recommended: already configured for the repo; needs org access).
3. License a self-hosted Developer/Enterprise edition.
