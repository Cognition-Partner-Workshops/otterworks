# Cutover runbook — OtterWorks billing estate → MongoDB Atlas (`ow_tp_mongodb_205236`)

Run `tp-run/mongodb-20260901T205236Z` · evidence pack `.migration/08_evidence_pack.md` (v2, **COMPLETE**, watermark
`74ecd69e`) · mapping v1.0.1 · tolerances v1 · canonicalization v1. This revision supersedes the v1 runbook written against
watermark `0150de08` (pre fix-pass). Secrets are referenced by **name only**. Devin never executes a production repoint; every
production-touching step below is executed by the **customer-held cutover principal**.

Executors used in this document:

- **CUSTOMER** — customer-held cutover principal (production Atlas project owner, application config/secret owner,
  Oracle DBA, DNS owner). Never held by Devin.
- **DEVIN** — migration principal only (read-only on Oracle `OW_BILLING`, Postgres `otterworks_demo`, DynamoDB; write
  only to `ow_tp_mongodb_205236` and `ow_tp_mongodb_205236_quarantine`). Steps are read-only or evidence-writing.

---

## A. Scope — what this repoint covers and what still reads legacy

### A.1 Covered (repointed to Atlas by this cutover)

| Surface | Code path | Collections read/written | Evidence |
|---|---|---|---|
| RPT-114 month-end **status** and **line** rollups | `services/legacy-billing/app/reports.py` `GET /api/reports/month-end` (`status_rows_mongo`, `line_rows_mongo`) | `invoices` (+`lines[]`), `codes` | wave1 (part1-u2) §2: 3 + 12 rows identical to `STATUS_SQL`/`LINE_SQL`, FM formatting |
| RPT-114 **balances** / reconciliation | `reports.py` `GET /api/reports/reconciliation` (`mongo_reconciliation`, `balances_pipeline`) | `customers`, `invoices` | wave1 §3: balances `(25000, 39799450.31, 7330214.66)` equal |
| `PKG_OW_UTIL` + `PKG_PLANS` rewrite | `ow_billing/util.py`, `ow_billing/plans.py`; routes `GET /api/plans`, `GET /api/tenants/<t>/entitlement`, `POST /api/tenants/<t>/plan-change` | `plans`, `tenants`, `subscriptions`, `subscriptions_history`, `codes`, `counters`, `billing_audit_log` | Tier-4 PLANS-001…005 5/5; single `counters` contract (`util.log_msg`, F-X-1 closed) |
| `PKG_RATING` rewrite | `ow_billing/rating.py` (Python entrypoints `compute_rating`, `fn_usage_summary`, `sp_finalize_rating`) — **no HTTP route** | `usage_events`, `subscriptions`, `plans`, `rating_periods` (+`results[]`), `billing_audit_log`, `counters` | Tier-4 RATING-001…008 8/8 |
| `PKG_INVOICING` rewrite | `ow_billing/invoicing.py` (`fn_invoice_preview`, `sp_issue_invoice`, `fn_invoice_lines`) — **no HTTP route** | `billing_invoices` (+`lines[]`), `credit_notes`, `rating_periods`, `tenants`, `billing_audit_log`, `counters` | Tier-4 INVOICE-001…006 6/6; F-U8-1 closed by PR #1457 (`lines[].invoice_id` emitted, fix-pass probes 17/17) |
| `PKG_DUNNING` rewrite | `ow_billing/dunning.py`; routes `GET /api/dunning/overdue`, `POST /api/dunning/schedule`, `POST /api/dunning/suspend`; `python -m ow_billing.jobs` (nightly, env-gated) | `billing_invoices`, `tenants`, `subscriptions`, `subscriptions_history`, `dunning_attempts`, `notifications`, `billing_audit_log`, `counters` | Tier-4 DUNNING-001…005 5/5 |
| Data only (no application read path repointed) | — | `documents` (+`versions[]`), `document_snapshots`, `files` | U3/U4 LIVE PASS; data parity only |

Atlas connection for all of the above: `MONGODB_ATLAS_URI` (via `ow_billing.mongo_client()` / `reports.mongo_db()`),
database `MONGODB_DB` (default `ow_tp_mongodb_205236`), namespace `MONGODB_NS` = `mongo_205236`,
`OW_BILLING_COLLECTION_PREFIX` must be **empty** in production (non-empty selects a replay clone).

### A.2 Still reads the legacy system after this cutover (explicit)

| Path | Reads | Why it is out of scope |
|---|---|---|
| `services/legacy-billing/app/app.py`: `/`, `/plans`, `/plans/<t>/entitlement`, `/plans/<t>/change`, `/health` | Postgres `billing.fn_list_plans/fn_entitlement/sp_change_plan`, `SELECT 1` | Calibration routes (mapping row 43); Mongo equivalents exist under `/api/plans`, `/api/tenants/*`. Not rewired. |
| `app.py`: `/api/rating/preview`, `/api/rating/finalize` | Postgres `billing.fn_usage_rating/sp_finalize_rating` | No Mongo HTTP route for rating; the `rating.py` module is callable in-process only. |
| `app.py`: `/api/invoices/<t>/preview`, `/api/invoices/<t>/issue`, `/api/invoices/<id>/lines` | Postgres `billing.fn_invoice_preview/sp_issue_invoice/fn_invoice_lines` | No Mongo HTTP route for invoicing. |
| `services/document-service` | Postgres `otterworks_demo` (`documents`, `document_versions`, `document_snapshots`) — reads **and writes** | Service never repointed; U3 delivered data parity only. If H.2 (d) is accepted, Postgres stays the system of record for documents after the window and Atlas `documents`/`document_snapshots` are a **point-in-time snapshot at the watermark** with no reader; a later repoint needs a fresh U3 load + recon, not a delta. |
| `services/file-service` (Rust) | DynamoDB `otterworks-file-metadata` — reads **and writes** | Service never repointed; U4 delivered data parity only. If H.2 (e) is accepted, DynamoDB stays the system of record for files after the window and Atlas `files` is a **point-in-time snapshot at the watermark** with no reader; a later repoint needs a fresh U4 load + recon, not a delta. |
| Oracle `JOB_NIGHTLY_DUNNING` | Oracle (disabled at source) | Its replacement `ow_billing/jobs.py` ships disabled; enabling it is step D.11. |

Consequence: this is a **partial-scope** cutover. Section H asks the customer to accept or reject each row of A.2.
During the window **all three** legacy stores (Oracle, Postgres, DynamoDB) are frozen (D.1) so the watermark and the D.2
idle check hold; after D.12 the frozen writers of any *accepted* A.2 row resume against their legacy store, and nothing
synchronises those writes into Atlas (no CDC exists).

---

## B. Preconditions (all must hold at the start of the window)

1. `.migration/08_evidence_pack.md` status is **COMPLETE** — it is, at watermark `74ecd69e` (pack §8: F-U8-1, F-X-1 and
   the wave-2b probe bundle closed with evidence; F-U8-2/F-U7-1 and partial scope carried as STOP C lines H.3 and H.2).
   If the run branch moves past `74ecd69e` before the window, the pack and this runbook are stale: a new parallel run and
   a new pack revision are required.
2. The independent audit of the evidence pack is **countersigned** (audit output attached to the STOP C request).
3. **STOP C approved for a NAMED window** (date, start/end UTC, approver). A prior STOP C approval, or an approval for a
   different window, **never carries over**; re-present section H for every new window.
4. Rollback dry run (section F.4) completed in the customer environment and its transcript attached.
5. The customer-held cutover principal, Oracle DBA, Postgres owner, AWS/IAM owner (file-service / DynamoDB) and DNS/config
   owner are named and present for the whole window.
6. Devin's migration principal remains read-only on legacy and write-scoped to the two migration databases; no
   production credential is issued to Devin.

---

## C. Freeze vs watermark

The legacy source is **idle/static**: no CDC exists, and the population was identical on all 8 reads across the
parallel run (`FIXTURE_META.INITIALIZED_AT 2026-09-01 20:53:10.961888`, `BILLING_AUDIT_LOG` 1 row,
`SEQ_BILLING_AUDIT_LOG` 2, `SEQ_SUBSCRIPTIONS_HIST` 1 before, between and after every cycle).

**Recommendation: FREEZE.** Declare the legacy estate read-only for all writers at the start of the window and cut over at
the recorded watermark. No delta load, no re-load (U2's loader has no staging swap — F-U2-2 — so a re-load after freeze is
not permitted).

| Watermark item | Value |
|---|---|
| Code | `74ecd69e98876b8da26336a6d7cc24eba3e74697` (run-branch head, all 10 units merged, post fix-pass merge `5fe2af81` of PR #1457 @ `7791a93e`) |
| Load | 2026-09-02 06:59:25 → 07:02:29 UTC |
| Source identity | seed `714559852` · `batch_no 85559852` · `source_ns demo` · manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` · `FIXTURE_META.INITIALIZED_AT 2026-09-01 20:53:10.961888` |
| Versions | mapping v1.0.1 `57de55f2…` · tolerances v1 `d67ccdda…` · canonicalization v1 `527cf87c…` |
| Final recon | cycle 3, 2026-09-02 07:11:21 → 07:16:00 UTC, GREEN (streak 3/3, red runs `[]`; cycles 1–2 07:02:43–07:06:42Z, 07:06:48–07:11:16Z) |
| Evidence | `tp-run/mongodb-20260901T205236Z--parallel-run-v2` @ `2443d6f5` (`evidence_log.md`, `final_recon_at_watermark.md`, `evidence/`) |
| Superseded | `0150de08` / `--parallel-run` @ `3279c93b` — not to be used |

If the source is found **not** idle at freeze (any count, sequence or `FIXTURE_META` differs from
`evidence/watermark/source_pass2.json`), stop: the watermark is invalid and a new parallel run is required.

---

## D. Repoint steps (executor named on every step)

| # | Step | Executor | Notes |
|---|---|---|---|
| D.0 | Confirm preconditions B.1–B.6; open the window log | CUSTOMER | Record window start UTC |
| D.1 | Freeze legacy — all three stores: revoke/suspend application write access to Oracle `OW_BILLING` and Postgres `otterworks_demo` (incl. `services/document-service`); suspend every `services/file-service` writer to DynamoDB `otterworks-file-metadata` (scale the service to zero or switch its IAM role to a read-only policy on the table — there is no in-app read-only flag); confirm `JOB_NIGHTLY_DUNNING` is DISABLED in `DBA_SCHEDULER_JOBS` | CUSTOMER (Oracle DBA, Postgres owner, AWS/IAM owner) | Legacy schema/data untouched; only writer access changes. The freeze holds until D.12 (or F.3.4); it is what makes D.2 meaningful |
| D.2 | Source idle check: re-read the 19 Oracle tables, 5 sequences, `FIXTURE_META`, Postgres 3 tables, DynamoDB `ns` histogram (`demo` = 10,000) with `tools/source_check.py`; diff against `evidence/watermark/source_pass2.json`; write result to the evidence branch | DEVIN (migration principal, read-only) | Any diff on any of the three stores → abort (section C); a DynamoDB diff means D.1 did not stop the file-service writers |
| D.3 | Target idle check: ns-scoped counts for the 18 mapped collections and 4 quarantine classes (`tools/guards.py`) equal section E.1 | DEVIN (read-only on target) | Any diff → abort |
| D.4 | Counters check (read-only): the 5 golden `counters` docs (`seq_billing_audit_log` 2, `seq_customer_master` 125000, `seq_customer_master_hist` 1, `seq_entity_attr_value` 11001, `seq_subscriptions_hist` 1) each have Int64 `seq` == `USER_SEQUENCES.LAST_NUMBER` read in D.2, and no document with `_id` `SEQ_*` or field `value` exists in any collection (`evidence/fix_acceptance_probe.txt` is the reference) | DEVIN (read-only) | Seeding is part of the watermark load (U1, F-X-1 closed); **no write in this step**. Any diff → abort |
| D.5 | Atlas connection-string swap: set the application secret **`MONGODB_ATLAS_URI`** in the target environment's config/secret store for `legacy-billing` to the production Atlas URI; set `MONGODB_DB=ow_tp_mongodb_205236`, `MONGODB_NS=mongo_205236`, ensure `OW_BILLING_COLLECTION_PREFIX` is unset/empty | CUSTOMER | Secret value never shared with Devin; Devin's own migration credential is **not** the production credential |
| D.6 | **Read-only phase:** feature flags for the five package rewrites stay **OFF** for every mutating route (`POST /api/tenants/<t>/plan-change`, `POST /api/dunning/schedule`, `POST /api/dunning/suspend`); `OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED` unset; only the **non-logging** read routes (`GET /api/tenants/<t>/entitlement`, `GET /api/dunning/overdue`, `GET /api/reports/*`) are routed to the new deployment; `GET /api/plans` is **withheld** (not routed / 503 at the ingress) until D.10 | CUSTOMER | Flags are deployment config of the customer environment; none exist in the repo. No business write can reach Atlas in this phase. **Audit-observer paths:** `fn_list_plans` (behind `GET /api/plans`) and `compute_rating` (called by `RATING-001` and, via `compute_preview`, by `INVOICE-001`) each append one `billing_audit_log` row and `$inc` `counters.seq_billing_audit_log` through the single `util.log_msg`, exactly as the Oracle originals do. Withholding `/api/plans` keeps live traffic from moving the audit count before E.1 is captured; the only audit writes before D.10 are E.4's, tallied as A in E.1 |
| D.7 | Rolling restart of `legacy-billing`; smoke with the non-logging read `GET /api/reports/month-end?ns=demo` → 200 with the E.3 rollup (pure aggregation, writes nothing). Do **not** use `GET /api/plans` as the smoke: it logs an audit row (a `LookupError: counter 'seq_billing_audit_log' is not seeded` here would mean D.4 was wrong → abort) | CUSTOMER | Note `/health` still checks Postgres (A.2) |
| D.8 | DNS / config: repoint the `legacy-billing` ingress/hostnames and any report consumer of RPT-114 to the deployment configured in D.5–D.7 (non-logging read routes only; `GET /api/plans` and every mutating route still withheld) | CUSTOMER | |
| D.9 | Run section E verification **in order E.1 → E.2 → E.3 → E.4 → E.5** against the production deployment and record results on the evidence branch. Through E.3 the target is exactly the watermark (no logging path has been called); E.4 appends the audit rows stated there. After E.5, run the read-only **first-cycle recon** exactly as specified in F.1 (U0–U5 gates + guards, no U6–U9 drivers, no loaders) and dump `billing_audit_log` and `counters` as the **post-verification baseline** for F.3.5 | DEVIN (read-only except the audit rows produced by E.4's replay) + CUSTOMER (RPT-114 via the production endpoint) | Any mismatch → section F (pure repoint-back; the only Atlas writes are the counted audit rows) |
| D.10 | **Enable writers — the point of no return (F.2) begins here.** Flip the feature flags ON for the mutating routes of PKG_OW_UTIL/PKG_PLANS and PKG_DUNNING; for PKG_RATING and PKG_INVOICING there is **no Mongo HTTP route** — either accept in-process-only use (H.2) or keep the legacy routes and record the partial scope | CUSTOMER | Only after D.9 is fully green |
| D.11 | Disable the Oracle dunning scheduler job permanently (`DBMS_SCHEDULER.DISABLE('JOB_NIGHTLY_DUNNING')`, already disabled at source — confirm) and, if PKG_DUNNING is in scope, schedule `python -m ow_billing.jobs nightly-dunning` with `OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED=true` in the application scheduler (`jobs.py` requires the `nightly-dunning` subcommand; without it the process exits with a usage error) | CUSTOMER | Activates the only unattended writer |
| D.12 | Declare cutover complete or rolled back; record window end UTC. Lift the D.1 freeze **only** for the legacy stores of A.2 rows accepted in H.2 (Postgres for document-service if (d) accepted; DynamoDB for file-service if (e) accepted; Postgres `billing.*` for the `app.py` routes if (a)–(c) accepted); Oracle `OW_BILLING` stays read-only (G.1) | CUSTOMER | Record which writers were re-enabled; from this point Atlas `documents`/`document_snapshots`/`files` are snapshots (A.2) |

---

## E. Immediate post-cutover verification (expected values from the watermark evidence)

All queries are ns-scoped (`{ns: "mongo_205236"}`) and read-only. Expected = cycle-3 final recon at the watermark.

### E.1 Counts per collection (`ow_tp_mongodb_205236`)

| Collection | Expected `countDocuments({ns})` | Embedded |
|---|---|---|
| `codes` | 32 | |
| `tenants` | 69 | |
| `plans` | 3 | |
| `customers` | 25,000 | Σ`attributes[]` 8,333 |
| `customers_history` | 0 | |
| `counters` | **5** before and **5** after E.4 (all loggers hit the one `seq_billing_audit_log` doc, which E.4 advances 2 → 4; the other four seeds unchanged: 125000, 1, 11001, 1) | |
| `invoices` | 18,750 | Σ`lines[]` 149,963 |
| `documents` | 2,000 | Σ`versions[]` 13,876 |
| `document_snapshots` | 384 | |
| `files` | 10,000 | |
| `subscriptions` | 69 | |
| `subscriptions_history` | 0 | |
| `usage_events` | 814 | |
| `rating_periods` | 3 | Σ`results[]` 3 |
| `billing_invoices` | 3 | Σ`lines[]` 2 |
| `credit_notes` | 5 | |
| `dunning_attempts` | 1 | |
| `notifications` | 1 | |
| `billing_audit_log` | 1 (`_id` 1, `PLANS`/`fn_list_plans`) **before E.4**; after E.4 exactly **3** (A = 2: `RATING-001` + `INVOICE-001`, both via `rating.compute_rating` → `util.log_msg`) with `log_id`s `{1, 3, 4}` — record the observed A in the window log | `counters.seq_billing_audit_log.seq` after E.4 = **4** (seed 2 + 2). `log_id` 2 is never issued (the seed equals Oracle's `LAST_NUMBER` and `log_msg` increments first — accepted, pack §6 F-FIX-2) |

E.1 and E.2 must be taken **before** any `GET /api/plans` or transcript replay; the 17 non-audit collections must stay
exact through the whole of section E. Also: `countDocuments({})` == `countDocuments({ns})` for every collection (count guard), and no `*__staging` or
`replay_u*_*` collection is read by production (replay clones may still exist; they are dropped in section G).

### E.2 Quarantine counts unchanged (`ow_tp_mongodb_205236_quarantine`)

| Class | Expected |
|---|---|
| `dirty_signup_dt` | 50 |
| `bad_csv_list` | 31 |
| `invoice_feed_orphan_lines` | 37 |
| `orphan_document_snapshots` | 6 |
| any other collection | none |

### E.3 RPT-114 parity on 3 tenants

`GET /api/reports/month-end?ns=demo` through the production endpoint must return exactly the watermark rollup:
status rows `issued 5,504 / 55,450,955.92`, `overdue 2,748 / 27,585,416.69`, `paid 10,498 / 104,582,085.97`;
12 line-type rows; `GET /api/reports/reconciliation?ns=demo` balances `(25000, 39799450.31, 7330214.66)`, `status: pass`.
Then, for three tenants chosen by the customer at the window (record ids in the window log), compare per-tenant
`(count, Σ total_amt)` over `invoices` against the legacy `STATUS_SQL` per-tenant result read by DEVIN with plain SQL
(`scripts/tp_mongo/rpt114_parity_u2.py` is the reference implementation). Expected: equal, FM-formatted strings identical.

### E.4 Transcript replays (one each, read-only transcripts, against the production database)

| Transcript | Expected |
|---|---|
| `RATING-001` (`fn_usage_rating`/`compute_rating` transcript — no business write, but `compute_rating` calls `log_msg`) | `business_fields` equal to the recorded Oracle transcript; side effect: exactly **1** `billing_audit_log` row (`RATING`, `log_id` **3**, from `counters.seq_billing_audit_log` 2 → 3) |
| `INVOICE-001` (`fn_invoice_preview` transcript — no business write, but `compute_preview` → `rating.compute_rating` → `log_msg`) | equal (unrounded, `tax/2` half-cents preserved); side effect: exactly **1** further `billing_audit_log` row (`RATING`, not `INVOICING`; `log_id` **4**, counter 3 → 4) |
| `DUNNING-001` (read-only `fn_overdue_accounts` transcript) | equal (money as `'161.29'`-style strings, order `issued_at, id`) |

`DUNNING-001` writes nothing (`fn_overdue_accounts` does not log). Total A after E.4 is therefore exactly 2; any other
value is a mismatch. All four packages log through the one `util.log_msg` contract (`counters._id: "seq_billing_audit_log"`,
field `seq`), so ids are monotonic across modules (fix-pass probe: `[3,4,5,6,7,8]` from seed 2); `/api/plans` stays
withheld until D.10 only so that live traffic does not move the audit tally during E. Mutating transcripts (`RATING-008`,
`INVOICE-003…006`, `DUNNING-002…005`) are **not** replayed against production; they were graded on the replay clones in the
final cycle (U8 T4 6/6 at `74ecd69e` includes the F-U8-1 fix: every rebuilt `billing_invoices.lines[]` carries
`invoice_id`; `evidence/fix_acceptance_probe.txt` shows 6 invoices / 17 lines / 0 missing on `replay_u8`). H.3 (F-U8-2/F-U7-1)
must be answered before writers are enabled at D.10.

### E.5 Audit log

`billing_audit_log` `countDocuments` == 3, `log_id`s `{1, 3, 4}`, max `log_id` == 4 == `counters.seq_billing_audit_log.seq`;
`seq_subscriptions_hist` unchanged at 1; every `billing_invoices.lines[].invoice_id == parent _id` (3 invoices / 2 lines);
no document with `_id` `SEQ_BILLING_AUDIT_LOG` or field `value` exists. Dump `billing_audit_log` and `counters` as the
post-verification baseline for F.3.5.

---

## F. Rollback

### F.1 Trigger

Roll back immediately on **any** of:

- any mismatch in E.1–E.5;
- any Tier-1 or Tier-2 RED in the **first-cycle recon** after the repoint, run inside the window **between D.9 and D.10**
  (i.e. before any writer is enabled, while the target must still equal the watermark). The first-cycle recon is the
  read-only subset of a parallel-run cycle — **not** `tools/cycle.sh`, whose U6–U9 steps re-load and Tier-4-replay the
  `replay_u*` clones (loader writes to the target database). Exact commands, all target-read-only, all against the golden
  (unprefixed) collections, `--mode live`, no `reset`:
  - `recon run --unit U0|U1|U2|U5 --family oracle --mapping <unit subset of 03_mapping_spec.json via tools/subset.py> --source-dsn-secret OW_BILLING_FIXTURE_DSN --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json --mode live --target-uri-secret MONGODB_ATLAS_URI --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo --out <dir>/U<n>/gate` (stock harness, Tiers 1–3 only);
  - `.migration/recon_ext/recon_pg.py --unit U3 --family postgres --mapping .migration/03_mapping_spec.json --unit-only --source-dsn-secret OW_PG_DSN <same common args>`;
  - `.migration/recon_ext/run_dynamo_recon.py --unit U4 --mapping .migration/03_mapping_spec.json --source-endpoint-secret AWS_ENDPOINT_URL <same common args>`;
  - `tools/guards.py <dir>` (ns count guard 18/18 + quarantine ceiling) and `tools/source_check.py` before/after.
  U5's Tiers 1–3 cover every golden collection owned by U6–U9 (`subscriptions`, `subscriptions_history`, `usage_events`,
  `rating_periods`, `billing_invoices`, `credit_notes`, `dunning_attempts`, `notifications`, `billing_audit_log`); the U6–U9
  Tier-4 drivers are **not** run against production — their evidence is the watermark cycles. Expected outputs: `result.json`
  `verdict: PASS` for U0–U5 with the cycle-3 tallies (pack §5) and `guards.json` PASS, with the one permitted delta that
  `billing_audit_log` = 3 / `counters.seq_billing_audit_log` = 4 if E.4 has already run (E.1). After D.10 no recon
  against the frozen source is meaningful; post-D.10 divergence is inventoried by F.3.5, not graded;
- loss of Atlas connectivity from the production deployment that is not restored within the window.

The rollback window is the named STOP C window plus the agreed grace period (H.4). Inside it every rollback is safe.

### F.2 Point of no return

The **first write accepted by the new stack that is not replayable to Oracle** — i.e. the first
`sp_change_plan` / `sp_finalize_rating` / `sp_issue_invoice` / `sp_schedule_dunning` / `sp_suspend_overdue` executed
against `ow_tp_mongodb_205236` by production traffic whose effect the customer will not re-key into Oracle. Until that
write, rollback is a pure repoint-back. After it, rollback requires the customer to replay or discard those writes; Devin
has no write path to Oracle and cannot do this.

Section D enforces this ordering: writers stay off through D.6–D.9 (read-only cutover, verification against the
unchanged watermark), and are enabled only at D.10–D.11 as the last acts of the window. Any rollback triggered before
D.10 is a pure repoint-back with nothing to replay.

### F.3 Repoint-back steps

| # | Step | Executor |
|---|---|---|
| F.3.1 | Flip the five package feature flags back to legacy routes; unschedule `python -m ow_billing.jobs` and unset `OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED` | CUSTOMER |
| F.3.2 | Restore the previous `legacy-billing` config/secret set (Postgres `DB_*`, no `MONGODB_ATLAS_URI` needed for legacy routes); rolling restart | CUSTOMER |
| F.3.3 | Revert DNS/ingress to the legacy deployment | CUSTOMER |
| F.3.4 | Lift the freeze on all three stores: restore application write access to Oracle `OW_BILLING`, Postgres `otterworks_demo` (document-service) and DynamoDB `otterworks-file-metadata` (file-service writers scaled back up / IAM policy restored); leave `JOB_NIGHTLY_DUNNING` in its pre-window state (DISABLED) | CUSTOMER (Oracle DBA, Postgres owner, AWS/IAM owner) |
| F.3.5 | If D.10 was reached: produce the **full change inventory** since the watermark — inserts, updates and deletes — by dumping every document of the 18 mapped collections (ns-scoped) plus `counters` and `billing_audit_log` and diffing against the watermark dump `evidence/load/` + cycle-3 `gate/` snapshots for the 17 non-audit collections and against the D.9 **post-verification baseline** for `billing_audit_log` and `counters` (`tools/subset.py` + the Tier-3 canonical diff, which compares full documents, not just `_id`s). Mutating entrypoints update pre-existing `subscriptions`, `subscriptions_history`, `rating_periods`, `billing_invoices`, `credit_notes`, `tenants` and `counters` documents in place, so an `_id`-only export is insufficient. Write the inventory to the evidence branch for the customer to replay into Oracle or discard | DEVIN (read-only on target, evidence-writing) |
| F.3.6 | Record the rollback, its trigger and timings in the window log; the Atlas target stays intact for triage | CUSTOMER |

Legacy data is untouched by cutover, so after F.3.4 the legacy estate is exactly the frozen state.

### F.4 Dry run (mandatory)

The customer **must exercise F.3.1–F.3.5 once as a dry run in the customer's environment before the window**
(precondition B.4), including the rolling restart, a legacy-route smoke test and one synthetic post-watermark write
(e.g. a plan change on a staging copy) to prove F.3.5 captures an in-place update, and attach the transcript to the
STOP C request.

---

## G. Decommission plan (after cutover is declared complete)

| # | Step | Executor | When |
|---|---|---|---|
| G.1 | Legacy stays **read-only** for the retention window for every store whose consumers were repointed: Oracle `OW_BILLING` always; Postgres `otterworks_demo` and DynamoDB `otterworks-file-metadata` only if H.2 (d)/(e) were answered "no" and those services were rewired — otherwise they remain live systems of record (A.2) and are **not** retired by this plan. No schema, data or job change on any legacy store | CUSTOMER | window end → retirement date |
| G.2 | Retirement date: **`<YYYY-MM-DD>` (placeholder — set at STOP C)** | CUSTOMER | |
| G.3 | Drop replay clones `replay_u6_*`, `replay_u7_*`, `replay_u8_*`, `replay_u9_*` from `ow_tp_mongodb_205236` (not read by production) | DEVIN (migration principal) | after first-cycle recon GREEN |
| G.4 | Revoke the migration principals: Devin's Atlas database user(s) for `ow_tp_mongodb_205236` / `_quarantine`; **Devin's Atlas API keys** (project-level); the secret `MONGODB_ATLAS_URI` as issued to Devin (rotate the production value if it was ever the same string) | CUSTOMER (Atlas project owner) | after the rollback window closes |
| G.5 | Revoke the read-only source accounts used by Devin: Oracle `ow_billing` fixture user / `OW_BILLING_FIXTURE_DSN`, Postgres read-only role on `otterworks_demo`, DynamoDB read policy on `otterworks-file-metadata` | CUSTOMER | same time as G.4 |
| G.6 | Archive the evidence branches (`--wave*-recon*` incl. `--wave2b-recon-part1:…/wave2b_probes/`, `--fix-recon`, `--parallel-run` (superseded), `--parallel-run-v2`, this branch) as tags; keep the quarantine database for the retention window, then drop | CUSTOMER | retirement date |
| G.7 | Retire legacy: decommission Oracle `OW_BILLING` after a final export; Postgres `otterworks_demo` and the DynamoDB table only once document-service / file-service have been repointed under a later STOP C (fresh U3/U4 load + recon at that time) | CUSTOMER | retirement date |

---

## H. STOP C decision lines (presented by the orchestrator; each needs an explicit yes/no)

| # | Decision | Answer |
|---|---|---|
| H.1 | Cut over **without live-write parity evidence** (no CDC; static source; parity proven only at the watermark by 3 GREEN cycles + Tier-4 transcripts on replay clones) — yes/no | ☐ yes ☐ no |
| H.2 | **Partial scope** — accept per row of §A.2: (a) `app.py` plan/entitlement/change routes stay on Postgres — yes/no; (b) rating has no Mongo HTTP route — yes/no; (c) invoicing has no Mongo HTTP route — yes/no; (d) document-service stays on Postgres, which resumes writes after D.12 and Atlas `documents`/`document_snapshots` become a watermark snapshot — yes/no; (e) file-service stays on DynamoDB, which resumes writes after D.12 and Atlas `files` becomes a watermark snapshot — yes/no | ☐ (a) ☐ (b) ☐ (c) ☐ (d) ☐ (e) |
| H.3 | **F-U8-2 / F-U7-1 behaviour decision** (the only carried finding; F-U8-1 and F-X-1 are closed — pack §8): on Mongo, `sp_finalize_rating` / `sp_issue_invoice` succeed for the 3 legacy-seeded periods of tenant 1 (`rating_periods._id` `4000…01/02/03`, not md5-derived) where Oracle raises `ORA-02291`. Choose one: **(i) accept** the Mongo behaviour as-is for those 3 periods, or **(ii) require** an Oracle-faithful rejection (code change + U7/U8 re-gate + new parallel run → new watermark before any window). A third option, loader-side id normalisation, changes data at the watermark and also requires a new parallel run | ☐ (i) accept ☐ (ii) fix + re-gate |
| H.4 | **Named window**: date, start–end UTC, approver; rollback grace period after window end | `<YYYY-MM-DD hh:mm–hh:mm UTC>`, approver `<name/role>`, grace `<h>` |
| H.5 | **Rollback condition** confirmed as §F.1 (any E.1–E.5 mismatch or any Tier-1/Tier-2 RED in the read-only first-cycle recon run between D.9 and D.10), with the dry run (F.4) attached | ☐ yes ☐ no |

A "no" on H.1 or H.5, or an unfilled H.4, blocks the window. A "no" on any H.2 row means that surface must be rewired and
re-gated before a new STOP C is presented. H.3 (ii) invalidates watermark `74ecd69e`: a new fix pass, parallel run and
pack revision are required before a window can be named.
