# Deployment disposition modules

These reusable modules and their PR-only validation pipelines implement the
**portfolio-disposition-standard** skill as the standard for disposition assessment
evidence and migration rationale.

| Module | Source pattern | Pipeline |
|---|---|---|
| `rehost` | `infrastructure/terraform/legacy-portal-ec2` | `.github/workflows/disposition-rehost.yml` |
| `rearchitect` | `infrastructure/terraform/legacy-portal-serverless` | `.github/workflows/disposition-rearchitect.yml` |
| `replatform` | Existing service charts in `infrastructure/helm/*` | `.github/workflows/disposition-replatform.yml` |

Each Terraform module is provider/backend agnostic and has a `ci/` root that plans
offline; each workflow validates without applying resources. The Helm workflow lints,
renders, and checks manifests without installing or upgrading a release. Use
`disposition_evidence` / `dispositionEvidence` to identify the assessment row that
supports the selected disposition.
