# OW Invoicing pipeline — analysis (run 1793185083, UNT18-3)

Source: `services/legacy-billing/db/oracle/` — `schema/01_tables.sql`,
`schema/02_horror.sql`, `schema/03_seed_static.sql`,
`packages/02_pkg_plans.sql`, `03_pkg_rating.sql`, `04_pkg_invoicing.sql`,
`01_pkg_util.sql` (callee names only). Namespace schema: `OW_BILLING`.
Live-verified read-only against Oracle on 2026-10-28 (`OW_BILLING_RO_DSN`):
20 tables / 25 indexes deployed; **no packages, triggers, or sequences are
deployed** — the PL/SQL bodies exist only in the repo SQL files, so routine
dependency rows below are source-derived (the estate's intended code), not
`ALL_OBJECTS`-derived.

## Scope and exclusions

In scope: `pkg_plans`, `pkg_rating`, `pkg_invoicing`, every table they read or
write, plus the bulk `INVOICE_HEADER` / `INVOICE_LINE` estate named by the
ticket.

Exclusions (named by the ticket; omitted from `calls` so the coverage rule
does not force a fake unit):
- `pkg_ow_util` — `LOG_MSG` (autonomous-transaction logger into
  `BILLING_AUDIT_LOG`) and `F_MD5_UUID` are called by five in-scope routines
  but are excluded; converted units substitute a target-side md5/uuid and
  drop logging. `BILLING_AUDIT_LOG` is therefore not a write target.
- `pkg_dunning`, `JOB_NIGHTLY_DUNNING`, `JOB_PURGE_AUDIT_LOG`
  (DBMS_SCHEDULER), CUSTBILL, analytics.
- `CUSTOMER_MASTER` (155 cols) is read only by the `u-invoice-quality-pipeline`
  expectation over `SIGNUP_DT` — no other unit reads it; only its quarantine
  object maps it.

## Unit inventory (4 units)

| unit | target_kind | tables (root_table) | routines |
|---|---|---|---|
| `u-plans` | lakebase | PLANS, TENANTS, SUBSCRIPTIONS, CODES, SUBSCRIPTIONS_HIST | FN_LIST_PLANS, FN_ENTITLEMENT, SP_CHANGE_PLAN, TRG_SUB_NO_UNCANCEL, TRG_SUBSCRIPTIONS_HIST |
| `u-rating` | lakebase | USAGE_EVENTS, RATING_PERIODS, RATING_RESULTS | COMPUTE_RATING, FN_USAGE_RATING, FN_USAGE_SUMMARY, SP_FINALIZE_RATING, TRG_USAGE_EVENTS_CHECK |
| `u-invoice-history` | delta | INVOICE_HEADER, INVOICE_LINE, INVOICES, INVOICE_LINES, CREDIT_NOTES | COMPUTE_PREVIEW, FN_INVOICE_PREVIEW, FN_INVOICE_LINES, SP_ISSUE_INVOICE |
| `u-invoice-quality-pipeline` | delta (DDL/pipeline-only) | quarantine sinks over INVOICE_LINE, INVOICE_HEADER, CUSTOMER_MASTER | `routines: []` |

Entry points (routines nothing in the batch calls → same-named
`deploy_objects` rows also in `write_targets`):
- w1 batch `u-plans`: FN_LIST_PLANS, FN_ENTITLEMENT, SP_CHANGE_PLAN,
  TRG_SUB_NO_UNCANCEL, TRG_SUBSCRIPTIONS_HIST.
- w2 batch `{u-rating, u-invoice-history}`: FN_USAGE_RATING,
  FN_USAGE_SUMMARY, TRG_USAGE_EVENTS_CHECK, FN_INVOICE_LINES,
  SP_ISSUE_INVOICE. `COMPUTE_RATING`, `SP_FINALIZE_RATING`,
  `COMPUTE_PREVIEW`, `FN_INVOICE_PREVIEW` are internal (called by roots or
  across the two units inside the batch) and get no deploy object.

## Wave / batch grouping — corrected vs proposal

`derive_waves.py --root . --namespace mig.invoicing` derives:

| wave | batch | units | write_targets |
|---|---|---|---|
| 1 | w1-b01 | u-invoice-quality-pipeline, u-plans | subscriptions, subscriptions_hist |
| 2 | w2-b01 | u-invoice-history, u-rating | credit_notes, invoice_lines, invoices, rating_periods, rating_results, usage_events |

**Change vs the ticket's proposal:** the table/routine lists per unit are
unchanged, but `u-rating` cannot sit in wave 1 while `u-invoice-history`
sits in wave 2. `pkg_invoicing.compute_preview` calls
`pkg_rating.compute_rating` and `pkg_invoicing.sp_issue_invoice` calls
`pkg_rating.sp_finalize_rating`, so u-invoice-history's transitive writes
include `RATING_PERIODS`/`RATING_RESULTS` (and `USAGE_EVENTS` via
`TRG_USAGE_EVENTS_CHECK` in the shared call graph). The two units form one
SCC and must batch together — placing u-invoice-history in a later wave
than u-rating is the only legal split *and* it still collides on the shared
write targets, so they must share wave 2. That frees the wave-1 slot the
edge-free, DDL-only `u-invoice-quality-pipeline` takes. Still four units,
two per wave. `u-rating`'s Lakebase target in a wave-2 batch beside a Delta
unit is a manifest-level note, not a spec violation.

If the manager prefers the quality pipeline to run *after* the invoice
snapshot it validates, `u-invoice-quality-pipeline` can move to wave 2/3
freely — it derives no edges (`routines: []`), so placement is unconstrained.

## Dependency table

`→` = cross-unit edge. Every callee row lives in the unit that owns the
package; `pkg_ow_util` callees are excluded per above.

| routine | reads | writes | calls |
|---|---|---|---|
| u-plans FN_LIST_PLANS | PLANS | — | — |
| u-plans FN_ENTITLEMENT | SUBSCRIPTIONS, PLANS, TENANTS | — | — |
| u-plans SP_CHANGE_PLAN | SUBSCRIPTIONS | SUBSCRIPTIONS | TRG_SUBSCRIPTIONS_HIST, TRG_SUB_NO_UNCANCEL |
| u-plans TRG_SUB_NO_UNCANCEL | — | SUBSCRIPTIONS | — |
| u-plans TRG_SUBSCRIPTIONS_HIST | SUBSCRIPTIONS | SUBSCRIPTIONS_HIST | — |
| u-rating COMPUTE_RATING | SUBSCRIPTIONS, PLANS, USAGE_EVENTS, RATING_RESULTS, RATING_PERIODS | — | — |
| u-rating FN_USAGE_RATING | — | — | COMPUTE_RATING |
| u-rating FN_USAGE_SUMMARY | USAGE_EVENTS | — | — |
| u-rating SP_FINALIZE_RATING | SUBSCRIPTIONS | RATING_PERIODS, RATING_RESULTS | COMPUTE_RATING |
| u-rating TRG_USAGE_EVENTS_CHECK | CODES | USAGE_EVENTS | — |
| u-invoice-history COMPUTE_PREVIEW | SUBSCRIPTIONS, PLANS, CREDIT_NOTES, TENANTS | — | → COMPUTE_RATING |
| u-invoice-history FN_INVOICE_PREVIEW | — | — | COMPUTE_PREVIEW |
| u-invoice-history FN_INVOICE_LINES | INVOICE_LINES | — | — |
| u-invoice-history SP_ISSUE_INVOICE | CREDIT_NOTES | INVOICES, INVOICE_LINES, CREDIT_NOTES | → SP_FINALIZE_RATING, FN_INVOICE_PREVIEW |

Data edges: `u-rating → u-plans` and `u-invoice-history → u-plans`
(they read SUBSCRIPTIONS, which u-plans writes). `u-invoice-history ↔
u-rating` (call edges, shared write targets) — the SCC.

## Type dictionary

| source shape | target | rules / evidence |
|---|---|---|
| `VARCHAR2(n)` | lakebase `VARCHAR` / delta `STRING` | `empty_string_is_null` |
| `CHAR(1)` (`*_YN`, POSTED_YN) | `CHAR(1)` / `STRING` | `rstrip_spaces`, `empty_string_is_null` |
| `NUMBER(p,0)` | `INT8` / `BIGINT` | `identity`; `census_fits_int64` |
| `NUMBER(p,s)` | `NUMERIC(p,s)` / `DECIMAL(p,s)` — (12,2) money, (12,6) overage_rate, (14,2) bulk money, (12,3) qty, (14,4) unit_price | `identity` |
| `DATE` (STARTS_ON, ENDS_ON, SUSPENDED_ON, PERIOD_*, ISSUED_ON) | `DATE` | `identity`; `census_midnight_only` — live census: 0 non-midnight values in every DATE column |
| `TIMESTAMP(6)` (OCCURRED_AT, CREATED_AT, ISSUED_AT) | `TIMESTAMP` / `TIMESTAMP_NTZ` | `identity` |
| `VARCHAR2(9)` 'DD-MON-YY' (SIGNUP_DT, INVOICE_DT, DUE_DT) | typed `DATE` + `<col>_raw` `STRING`/`VARCHAR` | `dd_mon_yy_or_null` on the typed col; `d-dirty-date-policy` |
| `VARCHAR2(20)` 'DD-MON-YY HH24:MI:SS' (HIST_DT) | `DATE` + `hist_dt_raw` | same dirty policy (values are a string timestamp) |
| `VARCHAR2(200)` GL_ACCT_CSV | `STRING` kept verbatim | `empty_string_is_null`; `csv_list` (multi-valued column, split deferred to consumers) |
| `VARCHAR2(20)` SERVICE_PERIOD 'MMYYYY-MMYYYY' | `STRING` | `empty_string_is_null`; `period_string_mmyyyy` |
| `SYS_REFCURSOR` returns | streaming row sets | entrypoints return cursors; converted units materialize the same columns |

## Resolved policies

- **Malformed-date policy** (`d-dirty-date-policy`): every `VARCHAR2` date
  column maps to a typed column parsed `DD-MON-YY`-or-NULL plus a
  `<col>_raw` string column preserving the source value verbatim. The
  Lakeflow expectation in `u-invoice-quality-pipeline` asserts the parse
  succeeds; violators land in the quarantine sink. Live census: 50 dirty
  `SIGNUP_DT` values (`VALIDATE_CONVERSION` catches semantically-bad values
  like `31-FEB-24` and `N/A`); `INVOICE_DT`/`DUE_DT` are currently clean —
  the expectation stands as the regression gate.
- **Orphan policy**: `INVOICE_LINE.INVOICE_ID → INVOICE_HEADER.INVOICE_ID`
  is unenforced; live census shows 37 orphans estate-wide. They are not
  dropped by the snapshot: `u-invoice-history` loads them verbatim and the
  quality pipeline's expectation routes them to `invoice_line_quarantine`.
  The package-side `INVOICE_LINES.INVOICE_ID → INVOICES` FK *is* enforced
  (`ON DELETE CASCADE`) — no orphan handling needed there.
- **Empty-input semantics**: Tenant One's slice is legitimately empty for
  all five `u-invoice-history` objects and for `SUBSCRIPTIONS_HIST` —
  live-verified 0 `INVOICES`/0 bulk rows for Tenant One. Snapshot loads
  still create the target tables (DDL always materializes); recon compares
  0=0. On the routine side, empty inputs return the source's own
  degenerate shapes: `fn_invoice_preview` emits five rows with NULL
  amounts when no plan covers the period; `compute_rating` yields NULL
  quota/rollover/overage with `used_units=0`; `sp_finalize_rating` still
  writes a `RATING_PERIODS` row (upsert) and a zeroed `RATING_RESULTS`
  row; `fn_entitlement`/`fn_usage_summary`/`fn_invoice_lines` return empty
  cursor sets.
- **Snapshot granularity**: one point-in-time full snapshot per object,
  Tenant-One-scoped where the column exists
  (`rerun_posture: not_applicable`; no watermark, no incremental merge).
  Tenant One literal: `tenant_id = '00000000-0000-0000-0000-000000000001'`.
  Tables without `tenant_id` filter by the parent's literal key list:
  `RATING_RESULTS` by `period_id IN` Tenant One's three period ids;
  `INVOICE_LINES` by `invoice_id NOT IN` the four non-Tenant-One invoice
  ids (its Tenant-One parent set is empty — `IN` needs ≥1 literal and the
  grammar has no subqueries, so the complement expresses the same empty
  slice and stays correct if Tenant One ever issues invoices). Reference
  tables PLANS/CODES are unfiltered global data. `u-invoice-quality-pipeline`
  carries **no** Tenant-One filter by design — its expectations must scan
  the full estate or they would be vacuous (Tenant One owns zero bulk
  rows).

## Tenant-One snapshot sizes (live-verified)

| object | rows for Tenant One | filter |
|---|---|---|
| plans | 3 (all) | none — reference |
| codes | all | none — reference |
| tenants | 1 | `id = '…0001'` |
| subscriptions | 1 | `tenant_id` |
| subscriptions_hist | 0 | `tenant_id` |
| usage_events | 1 | `tenant_id` |
| rating_periods | 3 | `tenant_id` |
| rating_results | 3 | `period_id IN` (3 period ids) |
| invoices | 0 | `tenant_id` |
| invoice_lines | 0 | `invoice_id NOT IN` (4 non-T1 ids) |
| credit_notes | 0 | `tenant_id` |
| invoice_header / invoice_line | 0 | `tenant_id` |
| quarantine sinks | 37 orphans + 50 dirty SIGNUP_DT (estate-wide) | none |

## Recon plan (one row per unit)

| unit | source mode | key | grading | determinism | projected legacy load |
|---|---|---|---|---|---|
| u-plans | snapshot read, Oracle RO | per-object PKs | full | deterministic (no nondeterministic funcs in spec path) | 5 SELECTs, ≤72 rows |
| u-rating | snapshot read | per-object PKs | full | deterministic | 3 SELECTs, ≤7 rows |
| u-invoice-history | snapshot read | per-object PKs | full | deterministic | 5 SELECTs, empty slices — DDL-only targets |
| u-invoice-quality-pipeline | snapshot read over full estate | sink PKs | `by_design_unverified` on all three sinks | deterministic | 3 scans of INVOICE_LINE (150k), INVOICE_HEADER (18.7k), CUSTOMER_MASTER (25k) |

Conversion notes for the wave workers (no code in this PR):
`pkg_rating`/`pkg_invoicing` package-state globals become per-call
parameters; `f_md5_uuid` keys → target-side `md5`/uuid; `log_msg` dropped;
`EXECUTE IMMEDIATE` static strings → plain DML; cursor-loop row-at-a-time
sums → set-based aggregates; `TRG_SUB_NO_UNCANCEL` (cancelled-stays-
cancelled) and `TRG_SUBSCRIPTIONS_HIST` (full-row version copies) deploy as
Lakebase triggers; `TRG_USAGE_EVENTS_CHECK` as a CHECK/expectation;
`INVOICE_LINES` rebuild = delete+insert per invoice (parity-proven
set-based SQL per the ticket, not scheduled).

## Defects / findings

None in the plugin for this step. `derive_waves` ran clean; all four
`mapping_spec.json` pass `recon.config.load_mapping_spec`.
