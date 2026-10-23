# Deployment disposition modules

These reusable modules and their PR-only validation pipelines implement the
**portfolio-disposition-standard** skill as the standard for disposition assessment
evidence and migration rationale.

| Module | Source pattern | Pipeline |
|---|---|---|
| `rehost` | `infrastructure/terraform/legacy-portal-ec2` | `.github/workflows/disposition-rehost.yml` |
| `rearchitect` | `infrastructure/terraform/legacy-portal-serverless` | `.github/workflows/disposition-rearchitect.yml` |
| `replatform` | Existing service charts in `infrastructure/helm/*` (bundled as `replatform/chart`) plus managed RDS, ElastiCache, S3, SQS and IRSA | `.github/workflows/disposition-replatform.yml` |

All three are Terraform modules. Each is backend agnostic and has an `example/` root to
copy and a `ci/` root that plans offline with mock credentials; every workflow runs on
`pull_request` only, checks that each planned AWS resource carries `run_token` and
`Expires` (`scripts/check-plan-tags.py`), and never applies. The replatform workflow also
lints and renders the bundled chart without installing a release. Set
`disposition_evidence` to the assessment-report row pointer that supports the
selected disposition (for example, `portfolio/assessment-report.csv:3`), not the
evidence list; it is stamped as an AWS tag value and must fit the 256-character tag
value limit and allowed character set.
