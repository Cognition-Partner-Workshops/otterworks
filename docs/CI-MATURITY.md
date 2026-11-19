# CI maturity assessment

This assessment covers the checked-in hardening configuration, not proof of successful
GitHub execution. Existing security fixtures and planted application bugs are unchanged.

| Area | Before | After | Remaining gap |
| --- | --- | --- | --- |
| Build/lint coverage | Polyglot, change-filtered service jobs; dashboard checks suppressed | Stable `CI gate` aggregates all 22 upstream jobs; skipped jobs allowed, failures/cancellations rejected | Industry-solutions has no CI job; coverage thresholds are not generally enforced |
| SAST | SonarCloud analysis triggered remediation without failing on ERROR | SonarQube/SonarCloud remains the enterprise-standard SAST gate; ERROR fails after remediation trigger completes | Missing token skips; unknown results warn/pass; timeouts warn and retain remediation behavior; Semgrep/CodeQL are supplementary; CodeQL excludes Kotlin and has no Scala matrix entry |
| Dependency/secret gates | PR-diff Trivy, Gitleaks commits, Semgrep baseline | Existing PR gates preserved; proposed ruleset names their exact checks | Historical findings are informational; report-service excluded from dependency scan |
| IaC/container configuration | Terraform validation; reusable sample policy/image checks | Trivy config scans infrastructure, platform, Helm/Kubernetes and Dockerfiles; SARIF uploaded | Existing 9 CRITICAL findings mean informational-only enforcement; image CVE scanning is not universal |
| Supply chain | Mixed action tags/SHAs; no Dependabot or Scorecard | CI/auto-remediation action references pinned; weekly ecosystem-grouped Dependabot; weekly/main Scorecard SARIF, no public result publishing | Not every older workflow/tool download is pinned; Scorecard does not enforce a score; Scala sbt is not supported by Dependabot |
| Workflow hardening | Missing permissions/timeouts/concurrency in several pipelines | CI, E2E, dependency, equivalence and parity workflows bounded and least-privilege; new scan/lint workflows similarly hardened | Other older workflows still need systematic review; actionlint now gates workflow changes |
| Branch protection | `Protect Main` ruleset exists with enforcement disabled; protection API returns 403 to this token | Importable default-branch ruleset requires PR, one approval, stale-review dismissal, resolved conversations and exact CI/security checks; blocks force-push/deletion | Owner must enable existing ruleset or import JSON; no remote settings changed; linear history intentionally not required |
| Ownership | No CODEOWNERS | No invented team identities | CODEOWNERS pending owner-provided team names |

## Proposed branch policy

Import [main-protection.json](../.github/rulesets/main-protection.json) through
[repository rulesets](https://github.com/Cognition-Partner-Workshops/otterworks/settings/rules).
The JSON is active *when imported*, not automatically applied by this commit.
Resolve/replace the existing disabled `Protect Main` ruleset rather than maintaining two policies.

Required check contexts are `CI gate`, `dependency-scan`, `secret-scan`, and `sast`.
The last three are the unrenamed job IDs/default check names in `security-scan.yml`,
not hypothetical labels such as “Dependency Vulnerability Scan”, “Gitleaks”, or “Semgrep”.
Confirm these check contexts on a PR before enabling enforcement. All approvals must be
fresh after subsequent pushes; code-owner reviews are not required until owners are known.

## IaC baseline and limits

Trivy 0.76.2, CRITICAL-only, local source scan (no cloud calls or deployments):

| Scan root | CRITICAL occurrences |
| --- | ---: |
| infrastructure | 6 |
| platform | 2 |
| services | 0 |
| frontend | 0 |
| demo-platform | 1 |
| migration | 0 |
| **Total** | **9** |

These are occurrences, not unique rule IDs. Findings include permissive Azure storage/key-vault
networking, HTTP ALB, unrestricted security-group egress and public EKS endpoints.
The workflow reports findings without blocking existing lab fixtures; scanner execution errors
still fail. SARIF upload requires code-scanning availability and is skipped for fork PRs.
Helm uses synthetic non-secret rendering values; secret creation is disabled and existing PV
creation is disabled for analysis only. This is not a deployed-configuration attestation.
The db2-archive chart still reports a YAML parse error in `templates/configmaps.yaml` and is
skipped by Trivy; Terraform also warns about unset deployment variables. These reduce coverage.
No application/chart fixes were made to hide these warnings or findings.

## Known application and automation gaps

- Admin-dashboard `npm ci` succeeded, but lint has no Angular `lint` target and tests returned
  `TOTAL: 7 FAILED, 75 SUCCESS` (UsersComponent timers/loading and AuthService assertions).
  Both existing `|| true` suppressions remain; planted bugs were not repaired.
- Dependabot covers actual manifests under services, all repository Dockerfiles, and Terraform
  roots/modules under infrastructure and platform. Weekly minor/patch updates are grouped per
  ecosystem, with five open version-update PRs per ecosystem entry. Major updates stay separate.
- Industry-solutions lacks dedicated build/tests; legacy-billing and Lambda modules rely on
  specialized parity/dependency harnesses rather than comprehensive per-service CI.
- CODEOWNERS, full Kotlin/Scala SAST coverage, enforced coverage thresholds and broader container
  CVE gates remain follow-up work. New workflows and SARIF ingestion need a real GitHub run.
