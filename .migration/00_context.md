# MongoDB migration engagement context

## Engagement facts

| Field | Value | Status |
|---|---|---|
| Repository | `Cognition-Partner-Workshops/otterworks` | FACT — user supplied |
| Immutable source branch | `tech-partnerships` at `c8bf45e59717c2d0ed45670aa0845f481fa5a5cd` | FACT — fetched from origin |
| Working branch | `tp-run/mongodb-20260901T033738Z` | FACT — created by repository policy |
| Source family/profile | Oracle / `mongo-migration/profiles/oracle.md` | FACT — user supplied |
| Scope | Every object found by the approved census, including schema, data, application SQL/ORM dependencies, PL/SQL, triggers, jobs, and business logic needed for cutover readiness | FACT — user supplied |
| Source access | Read-only assessment access only | FACT — user supplied |
| Target | MongoDB Atlas project `otterworks-demos`, cluster `otterworks-demo` | FACT — setup probe and approved platform context |
| Production repoint | Customer-held; Devin never executes or requests the cutover principal | FACT — user supplied |
| Correctness authority | Immutable baselines plus `mongo-recon-harness` machine-readable verdicts | FACT — user supplied |
| Explicit non-reference | `tech-partnerships-solutions` must not be consulted | FACT — user supplied |

## Topology

| Surface | Current understanding | Status |
|---|---|---|
| Source database | Oracle estate represented by `services/legacy-billing/db/oracle/`; live read-only endpoint is not yet available to this session | DISCOVERED |
| Application estate | OtterWorks code on the immutable source branch; exact SQL/ORM/procedure touchpoints are deferred to the approved census | FACT / pending census |
| Atlas control plane | Project, cluster, database-user, and access-list read/write/cleanup paths | WORKS — repository preflight |
| Atlas data plane | Temporary document insert/delete/drop over `MONGODB_ATLAS_URI` | WORKS — repository preflight |
| Migration namespace | Dedicated database `ow_tp_mongodb_20260901t033738z` on the approved Atlas cluster | PROPOSED |
| Capability-probe namespace | `ow_tp_preflight`, used only by the repository preflight and cleaned after each probe | PROPOSED |

## Interaction contract

- STOP A, STOP B, STOP C, and documented halt conditions are blocking decisions in this session.
- Questions are batched at each stop; each proposed row includes a recommended answer.
- Approval authority is the user in this session unless a later decision explicitly names another owner.
- Approval is valid only after it is recorded in `05_decisions.md`; chat history alone is not durable approval.
- Wave-close notices are posted in this session. No external Slack or Teams route is configured.
- Re-running `!mongo_migrate` derives the next action only from `.migration/`.

## Current phase

Phase 1 — migration setup. No inventory, modeling, migration, or recon work has started.
