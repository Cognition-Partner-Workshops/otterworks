# 04 — Progress Ledger (one screen; doubles as cutover readiness view)

Run `tp-run/mongodb-20260901T205236Z` · target DB `ow_tp_mongodb_205236` (`Q` = `..._quarantine`) · ns `mongo_205236`

## Registered write targets (register BEFORE any load; collision = halt)

Status `PLANNED` = declared at phase 2, no load may start until STOP B and the unit flips it to `REGISTERED`.

| Collection (db.coll) | Unit | Registered (UTC) | Status |
|---|---|---|---|
| `codes`, `tenants`, `plans` | U0 | 2026-09-01 21:18 | REGISTERED |
| `customers`, `customers_history`, `counters`, Q.`dirty_signup_dt`, Q.`bad_csv_list` | U1 | 2026-09-01 23:01 | REGISTERED |
| `invoices`, Q.`invoice_feed_orphan_lines` | U2 | planned | PLANNED |
| `documents`, `document_snapshots`, Q.`orphan_document_snapshots` | U3 | 2026-09-01 21:34 | REGISTERED |
| `files` | U4 | 2026-09-01 21:33 | REGISTERED |
| `subscriptions`, `subscriptions_history`, `usage_events`, `rating_periods`, `billing_invoices`, `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log` | U5 | 2026-09-02 00:20 UTC | REGISTERED |
| `replay_u6_*` (clone of U5 set for Tier-4 replay) | U6 | planned | PLANNED |
| `replay_u7_*` | U7 | planned | PLANNED |
| `replay_u8_*` | U8 | planned | PLANNED |
| `replay_u9_*` | U9 | planned | PLANNED |

## Units

| Wave | Unit | Status | Parity (result.json) | Quarantine rate | Unverified paths | Cost | PR |
|---|---|---|---|---|---|---|---|
| 0 | U0 reference (`codes`,`tenants`,`plans`) | MERGED | GREEN — LIVE PASS (wave0 recon @ `892eb88a`, re-loaded from head: T1 3/3, T2 14/14, T3 104/104 full diff, 42/42 probes; `tp-run/mongodb-20260901T205236Z--wave0-recon:.migration/recon/wave_reports/wave0.md`) | 0% (no quarantine targets declared; expected 0, observed 0) | Tier 4 app-level parity (no recorded ops for U0; `PKG_OW_UTL.F_CODE_DESC` / `fn_list_plans` read paths untouched — hand-replayed in recon §3.19–3.20 only); harness stratified-sampling path (populations below threshold → full diff); derived read-time `plans.tier` DECODE (unpersisted; graded by consuming unit) | 2 recon runs, 4 loads (child) + 1 LIVE re-load/recon (parent) | #1423 |
| 1 | U1 customers (XL) | MERGED | GREEN — LIVE PASS (wave1 recon part1 @ `c5baa80a`, re-loaded from head: T1 3/3, T2 313/313, T3 33,333/33,333 (25,000 customers full diff + 8,333 graded embedded `attributes` + 0 history), 56/56 probes; `tp-run/mongodb-20260901T205236Z--wave1-recon-part1:.migration/recon/wave_reports/wave1.md`) | 0.324% (50 `dirty_signup_dt` + 31 `bad_csv_list` of 25,000; rows retained verbatim, twins null; sets 50/50, 31/31 in recon) | LIVE gate (now covered by wave1 recon part1); Tier 4 app write path (`customer_writes.py` — scratch-customer smoke only, `write_path_smoke.json`); mapping `derived_ungraded` twins (`signup_date`, arrays, `addresses`, `phones`) unit-tested, not recon-graded; load swap atomic per collection, not across the five; RPT-114 Oracle-vs-aggregation parity once + Flask test client, not under gunicorn; `counters` (D11) graded vs `USER_SEQUENCES` outside harness | 2 recon runs (run 1 red: full-mapping run touched non-U1 `DOCUMENTS`; run 2 on U1 projection green), 3 loads (child) + 1 LIVE re-load/recon (parent) | #1430 |
| 1 | U2 invoices | NOT_STARTED | — | — | — | — | — |
| 1 | U3 documents (Postgres) | MERGED | GREEN — LIVE PASS (wave1 recon: T1 3/3, T2 18/18, T3 16,260/16,260 incl. 13,876 embedded versions; `tp-run/mongodb-20260901T205236Z--wave1-recon:.migration/recon/wave_reports/wave1.md`) | 1.54% (6/390 snapshots → Q.`orphan_document_snapshots`; 0.037% of unit rows) | LIVE gate (now covered by wave1 recon); Tier 4 (none in contract); adapter `key_strata` (full_diff path only); `state_b64` never decoded | 2 recon runs (run 1 red: adapter stat names) | #1420 |
| 1 | U4 files (DynamoDB) | MERGED | GREEN — LIVE PASS (wave1 recon pass 2 @ `3420f475`: T1 1/1, T2 12/12, T3 10,000/10,000 full diff; `tp-run/mongodb-20260901T205236Z--wave1-recon:.migration/recon/wave_reports/wave1.md`) | 0% (no quarantine; 40 `orphaned_metadata` markers retained, not quarantined) | `orphaned_metadata` via S3 `HeadObject` (HEAD path untested; storage-key convention used); file-service (Rust) read/write path against `files` not exercised (data-layer parity only); `folder_id` missing-attribute branch (`null_missing_equiv`); only partition `ns='demo'` in fixture table | 7 loads + 4 recons, ~6 min (child) + 1 LIVE re-load/recon (parent pass 2) | #1419 |
| 2 | U5 billing core | RECON_GREEN | GREEN — fixture PASS (T1 11/11, T2 53/53, T3 901/901 full diff incl. 3 embedded `results` + 2 embedded `lines`; `.migration/recon/U5/result.json`) | 0% (no quarantine targets declared; expected 0, observed 0) | LIVE gate (parent); Tier 4 app-level parity (PL/SQL not rewritten here — D10, U6–U9); `TRG_USAGE_EVENTS_CHECK` kind_cd-in-CODES branch not expressible in `$jsonSchema` (deferred to U7 write path); `counters` seeds for `SEQ_SUBSCRIPTIONS_HIST`/`SEQ_BILLING_AUDIT_LOG` not written (`counters` is U1's target; both sequences at 1); TTL expiry on `billing_audit_log` not observed (0 rows, index option verified); harness stratified-sampling path (all populations below threshold) | 2 loads + 1 recon run (child) | (this PR) |
| 2 | U6 PKG_OW_UTIL+PKG_PLANS (calibration) | NOT_STARTED | — | — | — | — | — |
| 2 | U7 PKG_RATING | NOT_STARTED | — | — | — | — | — |
| 3 | U9 PKG_DUNNING | NOT_STARTED | — | — | — | — | — |
| 3 | U8 PKG_INVOICING | NOT_STARTED | — | — | — | — | — |

Status values: NOT_STARTED · CONTRACT · LOADING · RECON_RED · RECON_GREEN · IN_REVIEW · MERGED · HALTED
