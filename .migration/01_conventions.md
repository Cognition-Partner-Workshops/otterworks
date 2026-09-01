# 01 — Conventions

## Designated write target

| Field | Value | Status |
|---|---|---|
| Atlas project | `otterworks-demos` (`MONGODB_ATLAS_PROJECT_ID`) | FACT |
| Atlas cluster | `otterworks-demo` (existing M0; no cluster creation, no tier change) | VERIFIED (`.tp-preflight/atlas-capabilities.json`, 8 probes / 0 denied) |
| Migration database | `ow_tp_mongodb_205236` | PROPOSED |
| Quarantine database | `ow_tp_mongodb_205236_quarantine` | PROPOSED |
| Namespace field | `ns: "mongo_205236"` on every migrated document | PROPOSED |
| Scale | SCALE=demo data (~230k source rows/items) fits M0 512 MB | FACT |

Only the two databases above may be written. No grants, users, cluster changes, or writes
to any other database. Every collection is registered in `04_progress.md` before its first
load. Loads are idempotent: drop-and-recreate the unit's collections in this run's
databases at the start of every run.

## Secret names (by name only, never by value)

| Tier | Purpose | Secret name |
|---|---|---|
| Assessment | Oracle / Postgres / DynamoDB fixtures | fixture-local dev credentials (see 00); no org secret |
| Migration | Atlas data plane | `MONGODB_ATLAS_URI` |
| Migration | Atlas control plane | `MONGODB_ATLAS_PUBLIC_KEY`, `MONGODB_ATLAS_PRIVATE_KEY`, `MONGODB_ATLAS_PROJECT_ID` |
| Cutover | Production repoint | customer-held; never available to Devin |

## MongoDB and application conventions

- Collections and fields: lower snake_case; collection names plural.
- `_id`: stable natural business key where externally referenced (customer_id, invoice_id,
  document_id, file_id); ObjectId otherwise — per the approved mapping spec (03).
- Oracle `NUMBER` → int/long/Decimal128 per 02; never double.
- Stored procedures: aggregation pipelines where behaviour is preserved, app-side logic
  (Python, matching `services/legacy-billing/app`) otherwise — PROPOSED, decided per package in 03.
- Driver languages in scope: Python (`pymongo`, legacy-billing + document-service), Rust
  (`mongodb` crate, file-service) — PROPOSED.
- Quarantine documents carry source key, unit, reason class, source watermark, `ns`.

## Branch and PR conventions

- Run branch: `tp-run/mongodb-20260901T205236Z`, cut from `tech-partnerships`.
- `tech-partnerships` and `main` are never PR targets.
- Unit branches: `migrate/ow_billing/<wave>-<unit>`.
- ONE PR per unit, never a stack; targets the run branch; passes `make tp-smoke`.
- PR bodies never identify the requesting user (multi-tenant account).
- A unit is complete only when MERGED with a green `result.json` verdict.

## PR evidence contract

Body ≤ ~2,000 chars, fixed order:

1. Unverified paths / declared-unexercised (top)
2. Decisions
3. Code
4. Evidence: rendered `recon.summary.md` (~30 lines); `result.json` and `report.md`
   linked, never pasted; recon mode, mapping version, tolerance version cited;
   idempotency proof; declared check populations; `PROFILE FEEDBACK` (may be empty).
