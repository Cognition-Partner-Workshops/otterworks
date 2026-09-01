# 04 — Progress Ledger (one screen; doubles as cutover readiness view)

Run `tp-run/mongodb-20260901T205236Z` · target DB `ow_tp_mongodb_205236` (`Q` = `..._quarantine`) · ns `mongo_205236`

## Registered write targets (register BEFORE any load; collision = halt)

Status `PLANNED` = declared at phase 2, no load may start until STOP B and the unit flips it to `REGISTERED`.

| Collection (db.coll) | Unit | Registered (UTC) | Status |
|---|---|---|---|
| `codes`, `tenants`, `plans` | U0 | 2026-09-01 21:40 (planned) | PLANNED |
| `customers`, `customers_history`, `counters`, Q.`dirty_signup_dt`, Q.`bad_csv_list` | U1 | planned | PLANNED |
| `invoices`, Q.`invoice_feed_orphan_lines` | U2 | planned | PLANNED |
| `documents`, `document_snapshots`, Q.`orphan_document_snapshots` | U3 | planned | PLANNED |
| `files` | U4 | 2026-09-01 21:33 | REGISTERED |
| `subscriptions`, `subscriptions_history`, `usage_events`, `rating_periods`, `billing_invoices`, `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log` | U5 | planned | PLANNED |
| `replay_u6_*` (clone of U5 set for Tier-4 replay) | U6 | planned | PLANNED |
| `replay_u7_*` | U7 | planned | PLANNED |
| `replay_u8_*` | U8 | planned | PLANNED |
| `replay_u9_*` | U9 | planned | PLANNED |

## Units

| Wave | Unit | Status | Parity (result.json) | Quarantine rate | Unverified paths | Cost | PR |
|---|---|---|---|---|---|---|---|
| 0 | U0 reference (`codes`,`tenants`,`plans`) | NOT_STARTED | — | — | — | — | — |
| 1 | U1 customers (XL) | NOT_STARTED | — | — | — | — | — |
| 1 | U2 invoices | NOT_STARTED | — | — | — | — | — |
| 1 | U3 documents (Postgres) | NOT_STARTED | — | — | — | — | — |
| 1 | U4 files (DynamoDB) | RECON_GREEN | PASS (fixture; `.migration/recon/U4/gate/result.json`) | 0% (no quarantine) | 4 (see `docs/tech-partnerships/recon/U4.recon.json`) | 7 loads + 4 recons, ~6 min | #1419 |
| 2 | U5 billing core | NOT_STARTED | — | — | — | — | — |
| 2 | U6 PKG_OW_UTIL+PKG_PLANS (calibration) | NOT_STARTED | — | — | — | — | — |
| 2 | U7 PKG_RATING | NOT_STARTED | — | — | — | — | — |
| 3 | U9 PKG_DUNNING | NOT_STARTED | — | — | — | — | — |
| 3 | U8 PKG_INVOICING | NOT_STARTED | — | — | — | — | — |

Status values: NOT_STARTED · CONTRACT · LOADING · RECON_RED · RECON_GREEN · IN_REVIEW · MERGED · HALTED
