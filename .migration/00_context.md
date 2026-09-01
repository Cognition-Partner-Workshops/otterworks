# 00 — Engagement Context

Run: `tp-run/mongodb-20260901T205236Z` (run tag `205236`). Opened 2026-09-01 by the
`[MONGO v1] Migration Orchestrator` (`!mongo_migrate`). A fresh run: nothing from earlier
`tp-run/mongodb-*` branches (approvals, ledgers, targets) carries over.

## Scope (FACT unless marked)

| Item | Value | Status |
|---|---|---|
| Engagement | OtterWorks billing estate → MongoDB Atlas, whole estate incl. PL/SQL packages | FACT |
| Source family | `oracle` (profile: plugin `skills/mongo-migration/profiles/oracle.md`) | FACT |
| Source system 1 | Oracle Database Free 23.26, PDB `FREEPDB1`, schema `OW_BILLING` | FACT |
| Source system 2 | Postgres 5432, database `otterworks`, schema `otterworks_demo` (documents, document_versions, document_snapshots) | FACT |
| Source system 3 | DynamoDB (LocalStack `:4566`), table `otterworks-file-metadata`, partition `ns = "demo"` | FACT |
| Source batch | Seeded `NS=demo`, `SCALE=demo`; manifest `testdata/legacy/manifests/demo.json` (seed `714559852`, batch_no `85559852`) | FACT |
| PL/SQL in scope | `PKG_UTIL`, `PKG_PLANS`, `PKG_RATING`, `PKG_INVOICING`, `PKG_DUNNING` (5 packages + bodies), 7 triggers, 2 scheduler jobs, 5 sequences | DISCOVERED |
| Object census (Oracle) | 20 tables, 25 indexes, 5 sequences, 5 packages, 7 triggers, 2 jobs (from `USER_OBJECTS`) | DISCOVERED |
| Target | Atlas project `otterworks-demos`, existing cluster `otterworks-demo` (M0) | FACT |
| Golden branch | `main` untouched; `tech-partnerships` is the before-state; migration lands on the run branch only | FACT |

## Source topology (pinned — drives fan-out shape)

| Fact | Value |
|---|---|
| Reachability | **VM-local.** All three sources are Docker fixtures on this session's VM (`localhost:52521`, `localhost:5432`, `localhost:4566`). Child sessions on other VMs cannot reach them. |
| Consequence | Source-dependent units run in-process in the orchestrator's session or in children that boot the same snapshot-baked fixture (`make oracle-billing-up && make oracle-billing-seed NS=demo`, `make infra-up && make seed-legacy NS=demo`). The fixture is deterministic (seed `714559852`), so a child that re-boots it compares against the same population; the manifest checksum proves it. |
| Source load cap | 1 concurrent recon/extract query per source (PROPOSED, see 02) |
| Recon mode | LIVE (dual connections, source + target) (PROPOSED, see 02) |

## Interaction contract (pinned once, never renegotiated)

| Event | Route |
|---|---|
| STOP A / B / C ready for approval | this session's chat (blocking) + Slack `#ow-migrations` (`C0BQP3P965V`) |
| Fan-out halt (circuit breaker, write-target collision, rerun-cap breach) | Slack `#ow-tp-alerts` (`C0BQP3LU3JT`) |
| Wave close (+ exception count, brief attached) | Slack `#ow-tp-status` (`C0BRYRE5ZQQ`) |
| Anything else | no ping |

Questions are batched per STOP with a recommended default per row; the requesting user
approves STOPs A and B; the customer cutover executor approves STOP C and executes the
production repoint with the customer-held principal. Silence is never approval.

## Principals

| Tier | Holder | Secrets (by name) |
|---|---|---|
| Assessment (read-only source) | Devin | fixture-local dev credentials (not org secrets): Oracle `ow_billing@localhost:52521/FREEPDB1`, Postgres `otterworks@localhost:5432/otterworks`, LocalStack test keys |
| Migration (Atlas write, scoped to this run's DBs) | Devin | `MONGODB_ATLAS_URI`, `MONGODB_ATLAS_PUBLIC_KEY`, `MONGODB_ATLAS_PRIVATE_KEY`, `MONGODB_ATLAS_PROJECT_ID` |
| Cutover (production repoint) | Customer | never held or requested by Devin |

Session: https://partner-workshops.devinenterprise.com/sessions/888c996e701e40e5885043a189111629
