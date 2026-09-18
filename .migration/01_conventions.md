# 01_conventions.md

- Designated migration database: `ow_billing` on the local Docker `mongo:7` container (`MONGO_LOCAL_URI`, localhost:27017). No other database, cluster, user or grant is written anywhere.
- Source: Oracle `OW_BILLING` in the local Docker container, read-only. Loaders open read-only sessions and only SELECT.
- Recon mode: `offline`. Evidence is fixture-only. A fixture PASS is never parity and never makes a unit merge-eligible for production.
- Branches: work branch `tp-run/mongodb-20260918T212022Z`. Unit branches `migrate/billing/w1-<unit>` off the work branch. PRs target the work branch only. Never main, never tech-partnerships.
- PR shape: Decisions, Code, Evidence. Unverified paths first. Under 2,000 characters. `recon.summary.md` rendered, raw JSON linked. Each unit PR states `live recon: not run, no source access`.
- Collections: snake_case, singular domain names (`customers`, `invoices`, `plans`, `codes`, `dunning_attempts`). Fields: snake_case, lowercased Oracle column names.
- Secrets by name only: `ORACLE_BILLING_DSN` (source, read-only), `MONGO_LOCAL_URI` (target). Values never appear in `.migration/`, PRs, or the walkthrough.
- Artifacts: `.migration/recon/<unit_id>/` redacted (harness default). No raw source rows are committed.
- Every plugin command runs as `env -u MONGODB_ATLAS_URI ...`.
