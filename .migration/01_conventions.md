# MongoDB target and delivery conventions

## Atlas target

| Convention | Value | Status |
|---|---|---|
| Atlas project | `otterworks-demos`, authenticated by secret `MONGODB_ATLAS_PROJECT_ID` | FACT |
| Atlas cluster | `otterworks-demo` | FACT |
| Migration database | `ow_tp_mongodb_20260901t033738z` | PROPOSED — unique per run |
| Capability-probe database | `ow_tp_preflight` | PROPOSED — temporary collections only |
| Collection naming | Lower-case plural `snake_case`; no unprefixed writes outside the two databases above | PROPOSED |
| Tenant/source namespace | Preserve the source namespace as an explicit `tenant_id` or mapping parameter; do not hard-code it into the mapping spec | PROPOSED |
| Atlas tier | Existing shared M0 (approximately 512 MB); modeling may proceed, but no load may begin until STOP B records measured fit or an M10+ target | FACT tier / PROPOSED guardrail |

## Modeling and implementation

| Convention | Value | Status |
|---|---|---|
| Driver | Official MongoDB driver already idiomatic to each owning service language | PROPOSED |
| Business logic | Move PL/SQL business rules into the owning application service by default; use aggregation pipelines for data-shaped set transformations | PROPOSED |
| Keys | Preserve externally visible natural/numeric keys; use ObjectId only where no external consumer depends on the Oracle sequence value | PROPOSED |
| Transactions | Prefer single-document atomicity; multi-document transactions require an approved mapping-spec row | PROPOSED |
| Loads | Idempotent upsert-by-key or isolated drop-and-reload, as declared per unit | PROPOSED |
| Quarantine | Write malformed or orphaned records to unit-owned quarantine collections with source key, reason code, and immutable source representation | PROPOSED |
| Source safety | Catalog and data access use a read-only assessment principal; no source schema/data writes | FACT |

## Git and PR delivery

| Convention | Value | Status |
|---|---|---|
| Run branch | `tp-run/mongodb-20260901T033738Z` from `origin/tech-partnerships` | FACT |
| Unit branch | `migrate/mongodb/<wave>-<unit>-20260901t033738z` | PROPOSED |
| PR target | `tp-run/mongodb-20260901T033738Z`; never `main` or `tech-partnerships` | FACT |
| PR granularity | One PR per migration unit; only an XL unit may use the playbook's decision-first contract PR plus implementation PR | FACT |
| PR body | Unverified paths first, then Decisions → Code → Evidence; about 2,000 characters maximum | FACT |
| Evidence | Render `recon.summary.md`; link `result.json` and `report.md`; cite mode, mapping version, and tolerance version | FACT |
| Merge gate | Machine-readable `mongo-recon-harness` PASS plus repository `make tp-smoke` | FACT |
| Review budget | Two review rounds per unit after the repository pre-PR self-check | FACT |

## Secret handling

Only secret names may appear in artifacts or commands. The migration principal uses
`MONGODB_ATLAS_PUBLIC_KEY`, `MONGODB_ATLAS_PRIVATE_KEY`,
`MONGODB_ATLAS_PROJECT_ID`, and `MONGODB_ATLAS_URI`. The read-only Oracle
assessment DSN is currently BLOCKED and must be supplied under a dedicated secret name.
No production cutover secret is held or requested.
