# Cutover runbook — OtterWorks billing estate → MongoDB Atlas (`ow_tp_mongodb_205236`)

Run `tp-run/mongodb-20260901T205236Z` · evidence pack `.migration/08_evidence_pack.md` · mapping v1.0.1 · tolerances v1 ·
canonicalization v1. Secrets are referenced by **name only**. Devin never executes a production repoint; every
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
| `PKG_OW_UTIL` + `PKG_PLANS` rewrite | `ow_billing/util.py`, `ow_billing/plans.py`; routes `GET /api/plans`, `GET /api/tenants/<t>/entitlement`, `POST /api/tenants/<t>/plan-change` | `plans`, `tenants`, `subscriptions`, `subscriptions_history`, `codes`, `counters`, `billing_audit_log` | Tier-4 PLANS-001…005 5/5 |
| `PKG_RATING` rewrite | `ow_billing/rating.py` (Python entrypoints `compute_rating`, `fn_usage_summary`, `sp_finalize_rating`) — **no HTTP route** | `usage_events`, `subscriptions`, `plans`, `rating_periods` (+`results[]`), `billing_audit_log`, `counters` | Tier-4 RATING-001…008 8/8 |
| `PKG_INVOICING` rewrite | `ow_billing/invoicing.py` (`fn_invoice_preview`, `sp_issue_invoice`, `fn_invoice_lines`) — **no HTTP route** | `billing_invoices` (+`lines[]`), `credit_notes`, `rating_periods`, `tenants`, `billing_audit_log`, `counters` | Tier-4 INVOICE-001…006 6/6 (F-U8-1 open) |
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
| `services/document-service` | Postgres `otterworks_demo` (`documents`, `document_versions`, `document_snapshots`) | Service never repointed; U3 delivered data parity only. |
| `services/file-service` (Rust) | DynamoDB `otterworks-file-metadata` | Service never repointed; U4 delivered data parity only. |
| Oracle `JOB_NIGHTLY_DUNNING` | Oracle (disabled at source) | Its replacement `ow_billing/jobs.py` ships disabled; enabling it is step D.11. |

Consequence: this is a **partial-scope** cutover. Section H asks the customer to accept or reject each row of A.2.

---

## B. Preconditions (all must hold at the start of the window)

1. `.migration/08_evidence_pack.md` status is **COMPLETE** — today it is **INCOMPLETE** (gaps §8: F-U8-1 fix + re-gate,
   F-X-1 counters contract + seed, F-U8-2 decision, wave-2b probe bundle committed). Either close each gap or carry it as
   an explicit STOP C line (section H).
2. The independent audit of the evidence pack is **countersigned** (audit output attached to the STOP C request).
3. **STOP C approved for a NAMED window** (date, start/end UTC, approver). A prior STOP C approval, or an approval for a
   different window, **never carries over**; re-present section H for every new window.
4. Rollback dry run (section F.4) completed in the customer environment and its transcript attached.
5. The customer-held cutover principal, Oracle DBA and DNS/config owner are named and present for the whole window.
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
| Code | `0150de08b072f15969a5a97da655a483b18ed939` (run-branch head, all 10 units merged) |
| Load | 2026-09-02 05:25:36 → 05:28:40 UTC |
| Source identity | seed `714559852` · `batch_no 85559852` · `source_ns demo` · manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` |
| Final recon | cycle 3, 2026-09-02 05:39:29 → 05:43:59 UTC, GREEN (streak 3/3, red runs `[]`) |
| Evidence | `tp-run/mongodb-20260901T205236Z--parallel-run` @ `3279c93b` |

If the source is found **not** idle at freeze (any count, sequence or `FIXTURE_META` differs from
`evidence/watermark/source_pass2.json`), stop: the watermark is invalid and a new parallel run is required.

---

## D. Repoint steps (executor named on every step)

| # | Step | Executor | Notes |
|---|---|---|---|
| D.0 | Confirm preconditions B.1–B.6; open the window log | CUSTOMER | Record window start UTC |
| D.1 | Freeze legacy: revoke/suspend application write access to Oracle `OW_BILLING` and Postgres `otterworks_demo`; confirm `JOB_NIGHTLY_DUNNING` is DISABLED in `DBA_SCHEDULER_JOBS` | CUSTOMER (Oracle DBA) | Legacy schema/data untouched; only writer access changes |
| D.2 | Source idle check: re-read the 19 Oracle tables, 5 sequences, `FIXTURE_META`, Postgres 3 tables, DynamoDB ns histogram with `tools/source_check.py`; diff against `evidence/watermark/source_pass2.json`; write result to the evidence branch | DEVIN (migration principal, read-only) | Any diff → abort (section C) |
| D.3 | Target idle check: ns-scoped counts for the 18 mapped collections and 4 quarantine classes (`tools/guards.py`) equal section E.1 | DEVIN (read-only on target) | Any diff → abort |
| D.4 | **If F-X-1 is closed:** seed `counters` docs for `SEQ_BILLING_AUDIT_LOG` and `SEQ_SUBSCRIPTIONS_HIST` from `USER_SEQUENCES.LAST_NUMBER − 1` read in D.2 (today 1 and 0) under the single agreed contract; record the seed in the evidence | DEVIN (writes only to `ow_tp_mongodb_205236.counters`) | If F-X-1 is open, skip and mark the audit log as unreliable in the window log (STOP C line H.3) |
| D.5 | Atlas connection-string swap: set the application secret **`MONGODB_ATLAS_URI`** in the target environment's config/secret store for `legacy-billing` to the production Atlas URI; set `MONGODB_DB=ow_tp_mongodb_205236`, `MONGODB_NS=mongo_205236`, ensure `OW_BILLING_COLLECTION_PREFIX` is unset/empty | CUSTOMER | Secret value never shared with Devin; Devin's own migration credential is **not** the production credential |
| D.6 | **Read-only phase:** feature flags for the five package rewrites stay **OFF** for every mutating route (`POST /api/tenants/<t>/plan-change`, `POST /api/dunning/schedule`, `POST /api/dunning/suspend`); `OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED` unset; only read routes (`GET /api/plans`, `GET /api/tenants/<t>/entitlement`, `GET /api/dunning/overdue`, `GET /api/reports/*`) are routed to the new deployment | CUSTOMER | Flags are deployment config of the customer environment; none exist in the repo. No business write can reach Atlas in this phase. **Audit-observer exception:** `GET /api/plans` (`fn_list_plans` → `util.log_msg`) and any `compute_rating` call append one `billing_audit_log` row and `$inc` the audit counter, exactly as the Oracle originals do — every such call made during D.7–D.9 is counted in the window log (see E.1) |
| D.7 | Rolling restart of `legacy-billing`; smoke with the non-logging read `GET /api/reports/month-end?ns=demo` → 200 with the E.3 rollup (pure aggregation, writes nothing). Do **not** use `GET /api/plans` as the smoke: it logs an audit row and, if D.4 was skipped, fails with `LookupError: counter 'seq_billing_audit_log' is not seeded` | CUSTOMER | Note `/health` still checks Postgres (A.2) |
| D.8 | DNS / config: repoint the `legacy-billing` ingress/hostnames and any report consumer of RPT-114 to the deployment configured in D.5–D.7 (read routes only) | CUSTOMER | |
| D.9 | Run section E verification **in order E.1 → E.2 → E.3 → E.4 → E.5** against the production deployment and record results on the evidence branch. Through E.3 the target is exactly the watermark (no logging path has been called); E.4 appends the audit rows stated there. After E.5, dump `billing_audit_log` and `counters` as the **post-verification baseline** for F.3.5 | DEVIN (read-only except the audit rows produced by E.4's replay) + CUSTOMER (RPT-114 via the production endpoint) | Any mismatch → section F (pure repoint-back; the only Atlas writes are the counted audit rows) |
| D.10 | **Enable writers — the point of no return (F.2) begins here.** Flip the feature flags ON for the mutating routes of PKG_OW_UTIL/PKG_PLANS and PKG_DUNNING; for PKG_RATING and PKG_INVOICING there is **no Mongo HTTP route** — either accept in-process-only use (H.2) or keep the legacy routes and record the partial scope | CUSTOMER | Only after D.9 is fully green |
| D.11 | Disable the Oracle dunning scheduler job permanently (`DBMS_SCHEDULER.DISABLE('JOB_NIGHTLY_DUNNING')`, already disabled at source — confirm) and, if PKG_DUNNING is in scope, schedule `python -m ow_billing.jobs nightly-dunning` with `OW_BILLING_JOB_NIGHTLY_DUNNING_ENABLED=true` in the application scheduler (`jobs.py` requires the `nightly-dunning` subcommand; without it the process exits with a usage error) | CUSTOMER | Activates the only unattended writer |
| D.12 | Declare cutover complete or rolled back; record window end UTC | CUSTOMER | |

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
| `counters` | 3 (U1 docs) — **5 if D.4 executed** | |
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
| `billing_audit_log` | 1 (`_id` 1, `PLANS`/`fn_list_plans`) **before E.4**; after E.4 exactly 1 + A, where A = audit rows logged by E.4 (see there) plus any `GET /api/plans` calls recorded in the window log | `counters.seq_billing_audit_log.seq` (if seeded in D.4) advances by the same A |

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
| `RATING-001` (`fn_usage_rating`/`compute_rating` transcript — no business write, but `compute_rating` calls `log_msg`) | `business_fields` equal to the recorded Oracle transcript; side effect: exactly **1** `billing_audit_log` row (`RATING`) if the counter was seeded in D.4, **0** if not (`rating.log_msg` swallows the failure) — record A accordingly |
| `INVOICE-001` (read-only `fn_invoice_preview` transcript) | equal (unrounded, `tax/2` half-cents preserved) |
| `DUNNING-001` (read-only `fn_overdue_accounts` transcript) | equal (money as `'161.29'`-style strings, order `issued_at, id`) |

`INVOICE-001` and `DUNNING-001` write nothing (`fn_invoice_preview` and `fn_overdue_accounts` do not log). Mutating
transcripts (`RATING-008`, `INVOICE-003…006`, `DUNNING-002…005`) are **not** replayed against production; they were
graded on the replay clones in the final cycle.

### E.5 Audit log

If D.4 executed: `counters` docs present under the agreed contract, `billing_audit_log` max `_id` == counter value, and
`countDocuments` == 1 + A with A as tallied in the window log. If D.4 skipped: `billing_audit_log` still 1, and record
"audit log unreliable until F-X-1 closed" in the window log. Either way, dump both collections as the post-verification
baseline.

---

## F. Rollback

### F.1 Trigger

Roll back immediately on **any** of:

- any mismatch in E.1–E.5;
- any Tier-1 or Tier-2 RED in the first-cycle recon run after cutover (`tools/cycle.sh` in read-only mode against the
  production database) within the rollback window;
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
| F.3.4 | Lift the freeze: restore application write access to Oracle `OW_BILLING` / Postgres `otterworks_demo`; leave `JOB_NIGHTLY_DUNNING` in its pre-window state (DISABLED) | CUSTOMER (Oracle DBA) |
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
| G.1 | Legacy stays **read-only** (Oracle `OW_BILLING`, Postgres `otterworks_demo`, DynamoDB `otterworks-file-metadata`) for the retention window; no schema, data or job change | CUSTOMER | window end → retirement date |
| G.2 | Retirement date: **`<YYYY-MM-DD>` (placeholder — set at STOP C)** | CUSTOMER | |
| G.3 | Drop replay clones `replay_u6_*`, `replay_u7_*`, `replay_u8_*`, `replay_u9_*` from `ow_tp_mongodb_205236` (not read by production) | DEVIN (migration principal) | after first-cycle recon GREEN |
| G.4 | Revoke the migration principals: Devin's Atlas database user(s) for `ow_tp_mongodb_205236` / `_quarantine`; **Devin's Atlas API keys** (project-level); the secret `MONGODB_ATLAS_URI` as issued to Devin (rotate the production value if it was ever the same string) | CUSTOMER (Atlas project owner) | after the rollback window closes |
| G.5 | Revoke the read-only source accounts used by Devin: Oracle `ow_billing` fixture user / `OW_BILLING_FIXTURE_DSN`, Postgres read-only role on `otterworks_demo`, DynamoDB read policy on `otterworks-file-metadata` | CUSTOMER | same time as G.4 |
| G.6 | Archive the evidence branches (`--wave*-recon*`, `--parallel-run`, this branch) as tags; keep the quarantine database for the retention window, then drop | CUSTOMER | retirement date |
| G.7 | Retire legacy: decommission Oracle `OW_BILLING`, Postgres `otterworks_demo`, DynamoDB table after a final export | CUSTOMER | retirement date |

---

## H. STOP C decision lines (presented by the orchestrator; each needs an explicit yes/no)

| # | Decision | Answer |
|---|---|---|
| H.1 | Cut over **without live-write parity evidence** (no CDC; static source; parity proven only at the watermark by 3 GREEN cycles + Tier-4 transcripts on replay clones) — yes/no | ☐ yes ☐ no |
| H.2 | **Partial scope** — accept per row of §A.2: (a) `app.py` plan/entitlement/change routes stay on Postgres — yes/no; (b) rating has no Mongo HTTP route — yes/no; (c) invoicing has no Mongo HTTP route — yes/no; (d) document-service stays on Postgres — yes/no; (e) file-service stays on DynamoDB — yes/no | ☐ (a) ☐ (b) ☐ (c) ☐ (d) ☐ (e) |
| H.3 | Carried findings — for each: fix + re-gate before the window, or accept: F-U8-1 (`lines[].invoice_id` omitted on issue); F-X-1 (`counters` contract/seed; audit log unreliable if open); F-U8-2/F-U7-1 (Mongo issues invoices for 3 legacy-seeded periods Oracle refuses) | ☐ fix ☐ accept, per finding |
| H.4 | **Named window**: date, start–end UTC, approver; rollback grace period after window end | `<YYYY-MM-DD hh:mm–hh:mm UTC>`, approver `<name/role>`, grace `<h>` |
| H.5 | **Rollback condition** confirmed as §F.1 (any E.1–E.5 mismatch or any Tier-1/Tier-2 RED in the first-cycle recon within the window), with the dry run (F.4) attached | ☐ yes ☐ no |

A "no" on H.1 or H.5, or an unfilled H.4, blocks the window. A "no" on any H.2 row means that surface must be rewired and
re-gated before a new STOP C is presented.
