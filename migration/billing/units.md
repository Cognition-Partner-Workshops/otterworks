# Migration units and waves (plan step `s3.3-unit-derivation`)

Run branch `tp-run/mongodb-20261001T233613Z`. A unit is a coherent code slice
plus the collections it owns. The five units below partition the 16
collections / 21 secondary indexes of `migration/billing/mapping_spec.json`
(#1775, dispositions #1776), the 19 migrate-bucket tables of
`migration/billing/census.json`, the 12 PL/SQL entrypoints of
`migration/billing/access_patterns.md` and the 14 routes of
`docs/tech-partnerships/contracts/billing-facade.contract.json`. The
machine-readable form is `migration/billing/units/units.json`; `python3
migration/billing/units/check.py` proves the partition (every collection,
table, entrypoint and route in exactly one unit; indexes sum to 21; every
atomic unit intra-unit or a declared cross-unit edge; every cite below
resolves). The human accepts this model via gate `g-model-accepted`.

Decision in force, not reopened: **d-logic-home** - the Mongo backend lives in
the legacy-billing facade, i.e. a `backends/mongo.py` module picked by
`BILLING_BACKEND=mongo` in `services/legacy-billing/app/backends/__init__.py:5-11`.
Oracle `OW_BILLING` stays read-only; Atlas writes go only to
`ow_tp_billing_20261001T233613Z` via `MONGODB_ATLAS_URI` (by name).

## Summary

| unit | name | wave | ticket | collections (indexes) | source tables | live rows |
|------|------|------|--------|-----------------------|---------------|-----------|
| U1 | foundation | 1 | UNT-15 (`s4.1.b01`) | `codes`, `tenants`, `plans`, `subscriptions`, `subscriptions_hist` (4) | CODES, TENANTS, PLANS, SUBSCRIPTIONS, SUBSCRIPTIONS_HIST | 173 |
| U2 | customers | 2 | UNT-18 (`s4.2.b01`) | `customers`, `customers_hist` (4) | CUSTOMER_MASTER, ENTITY_ATTR_VALUE, CUSTOMER_MASTER_HIST | 33,333 |
| U3 | rating | 2 | UNT-19 (`s4.2.b02`) | `usage_events`, `rating_periods` (2) | USAGE_EVENTS, RATING_PERIODS, RATING_RESULTS | 820 |
| U4 | invoicing | 2 | UNT-20 (`s4.2.b03`) | `invoices`, `credit_notes`, `invoice_feed`, `invoice_feed_quarantine` (8) | INVOICES, INVOICE_LINES, CREDIT_NOTES, INVOICE_HEADER, INVOICE_LINE | 168,760 |
| U5 | dunning | 2 | UNT-21 (`s4.2.b04`) | `dunning_attempts`, `notifications`, `billing_audit_log` (3) | DUNNING_ATTEMPTS, NOTIFICATIONS, BILLING_AUDIT_LOG | 2 |

16 collections, 21 indexes, 19 tables (`FIXTURE_META` is out of scope per the
census). Live rows are the census `COUNT(*)` at capture; U2 and U4 carry the
volume (`CUSTOMER_MASTER` 25,000 + `ENTITY_ATTR_VALUE` 8,333; `INVOICE_HEADER`
18,750 + `INVOICE_LINE` 150,000), the rest is fixture-sized.

## Waves

- **Wave 1 = U1.** Everything else reads `codes`/`plans`/`tenants`/`subscriptions`,
  calls the tenant bootstrap, or needs the backend module and the `mongo:7`
  fixture to exist. Readiness UNT-14, verify UNT-16.
- **Wave 2 = U2, U3, U4, U5** in parallel on U1. Readiness UNT-17, verify UNT-22.
  Two intra-wave couplings to schedule inside the wave (not new waves):
  - U4 -> U3: `sp_issue_invoice` finalizes the rating period inside its own
    transaction (`PKG_INVOICING` depends on `PKG_RATING`,
    `services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql:134`; spec
    `atomic_units.issue_invoice` writes `rating_periods`). Merge U3 before U4,
    or U4 carries the finalize step until U3 lands.
  - U5 -> U4: `overdue` / `schedule_dunning` / `suspend_overdue` read
    `invoices`; U5's live recon needs U4's `invoices` loaded. Checked in UNT-22.

Every other cross-unit edge points at wave 1 (listed per unit below and in
`units.json#cross_unit`). The audit writer is the one shared write: every
module appends to `billing_audit_log` outside its transaction
(`access_patterns.md`, autonomous `log_msg`); U1 ships the helper, U5 owns the
collection.

## U1 foundation (wave 1)

Owns `codes`, `tenants`, `plans`, `subscriptions`, `subscriptions_hist`
(reference + plan state + its history; `d-history-tables`). Indexes
`uq_tenants_name`, `uq_plans_code`, `ix_subscriptions_tenant_starts`,
`ix_subscriptions_hist_subscription`.

- Scaffolding: `backends/mongo.py` skeleton selected by `BILLING_BACKEND=mongo`
  (`services/legacy-billing/app/backends/__init__.py:5-11`); a `mongo:7`
  fixture service in `docker-compose.tp.yml:6-14` next to `legacy-billing` and
  in the `legacy-billing` job of `.github/workflows/tp-golden-smoke.yml:99-110`
  (pymongo added to the `uv run` deps); `make tp-smoke` (`Makefile:304`) stays
  green on both backends. The fixture is development scaffolding only, never
  merge evidence.
- Logic: `PKG_PLANS` (`fn_list_plans`, `fn_entitlement`, `sp_change_plan`;
  `services/legacy-billing/app/backends/oracle.py:56-82`), the tenant bootstrap
  `ensure_tenant` (tenant + initial subscription,
  `services/legacy-billing/app/backends/oracle.py:134-172`), and the shared
  helpers of `PKG_OW_UTIL` (`f_code_desc`, `f_dt2str`/`f_str2dt`, `f_md5_uuid`,
  the `log_msg` audit writer). `TRG_SUBSCRIPTIONS_HIST` becomes the pre-image
  copy inside the `change_plan` transaction; `TRG_SUB_NO_UNCANCEL` (status 30
  never changes) becomes a service invariant. `SEQ_SUBSCRIPTIONS_HIST` retires.
- Routes: `GET /plans`, `GET /me`, `GET /entitlement`, `POST /plan-change`
  (`services/legacy-billing/app/facade.py:72-195`) and the legacy
  `/health`, `/`, `/plans`, `/plans/<tenant_id>/entitlement`,
  `/plans/<tenant_id>/change` (`services/legacy-billing/app/app.py:13-41`).
- Atomic unit: `change_plan` = `subscriptions` + `subscriptions_hist`
  (multi-document transaction), intra-unit.
- Cross-unit: `GET /me` also reads one `customers` row
  (`services/legacy-billing/app/facade.py:118-126`); on the Mongo backend its
  `customer` key is null until U2 lands, so parity of that key is a wave-2 check.

## U2 customers (wave 2)

Owns `customers` (`CUSTOMER_MASTER` flat + `ENTITY_ATTR_VALUE` as
`attributes[]`; `d-flat-customer-columns`, `d-customer-eav`) and
`customers_hist`. Indexes `ix_customers_tenant_seq`,
`ix_customers_conversion_batch`, `uq_customers_attributes_eav_id`,
`ix_customers_hist_cust`.

- Code: the customer-field routes - `GET /customer`
  (`services/legacy-billing/app/facade.py:277-303`, facade-side SQL, no PL/SQL
  entrypoint) and the `customer` sub-document of `GET /me`.
- Logic: `TRG_CUSTOMER_MASTER_SEQ` keeps its derivation part (`cust_name_upper`,
  `row_version_no` default); `TRG_CUSTOMER_MASTER_HIST` becomes application-side
  versioning. Retired: `SEQ_CUSTOMER_MASTER` (values travel as data),
  `SEQ_CUSTOMER_MASTER_HIST`, `SEQ_ENTITY_ATTR_VALUE`, `TRG_ENTITY_ATTR_VALUE_SEQ`.
- No atomic unit of its own. Cross-unit: reads `codes` (U1, wave 1); is read
  by U4's CUSTBILL extract and reconciliation report (both wave 2).

## U3 rating (wave 2)

Owns `usage_events` (`d-reference-usage-events`) and `rating_periods` with the
embedded `result` (`RATING_RESULTS`, `d-embed-rating-result`). Indexes
`ix_usage_events_tenant_occurred`, `uq_rating_periods_tenant_start`.

- Logic: `PKG_RATING` (`fn_usage_rating`, `fn_usage_summary`,
  `sp_finalize_rating`; `services/legacy-billing/app/backends/oracle.py:83-103`);
  package-global rating state between compute and finalize becomes per-request
  state. `TRG_USAGE_EVENTS_CHECK` (units > 0, `kind_cd` in `CODES('USAGE_KIND')`)
  becomes service/schema validation.
- Code: `GET /usage` and `POST /internal/usage/events`
  (`services/legacy-billing/app/facade.py:196-229`,
  `services/legacy-billing/app/facade.py:355-400`), the legacy
  `/api/rating/preview` and `/api/rating/finalize`
  (`services/legacy-billing/app/app.py:44-55`), and the usage bridge
  (`services/legacy-billing/bridge/bridge.py:19-20`, SQS -> `/internal/usage/events`).
- Atomic unit: `finalize_rating` = one `rating_periods` document (header +
  `result`), atomic by construction.
- Cross-unit: usage ingest calls `ensure_tenant` and rating reads
  `plans`/`subscriptions`/`codes` (U1, wave 1); `rating_periods` is written by
  U4's `issue_invoice` (see Waves).

## U4 invoicing (wave 2)

Owns `invoices` (lines embedded, `d-embed-invoice-lines`), `credit_notes`,
and - as directed by this ticket - `invoice_feed` (`INVOICE_HEADER` with
`INVOICE_LINE` embedded, `d-feed-embed-lines`) and `invoice_feed_quarantine`
(orphan `INVOICE_LINE` rows). Indexes `ix_invoices_tenant_issued`,
`ix_invoices_status_issued`, `uq_invoices_lines_id`,
`ix_credit_notes_tenant_issued`, `ix_invoice_feed_batch`,
`ix_invoice_feed_status_due` (build deferred), `uq_invoice_feed_lines_line_id`,
`ix_invoice_feed_quarantine_invoice`.

- Logic: `PKG_INVOICING` (`fn_invoice_preview`, `fn_invoice_lines`,
  `sp_issue_invoice`; `services/legacy-billing/app/backends/oracle.py:104-121`).
- Code: `GET /invoices`, `GET /invoices/<invoice_id>/lines`
  (`services/legacy-billing/app/facade.py:230-276`); the legacy
  `/api/invoices/<tenant_id>/preview`, `/api/invoices/<tenant_id>/issue`,
  `/api/invoices/<invoice_id>/lines` (`services/legacy-billing/app/app.py:57-79`).
- Admin reports in `services/legacy-billing/app/reports.py` (this ticket): the
  three report pairs `month-end`, `reconciliation`, `finance`
  (`services/legacy-billing/app/reports.py:159-286`) and their SQL
  (`STATUS_SQL`, `LINE_SQL`, `BALANCES_SQL`,
  `services/legacy-billing/app/reports.py:42-100`) move from
  `INVOICE_HEADER`/`INVOICE_LINE`/`CUSTOMER_MASTER` to `invoice_feed` and
  `customers` aggregations; `reconciliation` stops reporting `status: baseline`
  and returns pass|fail with per-check results, as its comment already
  promises. `finance` keeps reading the published CSV.
- CUSTBILL extract: `make tp-month-end` (`Makefile:637-656`) and
  `etl/legacy-extra/tools/oracle_custbill_extract.py:15-29` (header + customer
  + tenant join) read Atlas on the Mongo backend; the ksh/Perl chain after the
  extract is unchanged.
- Atomic unit: `issue_invoice` = `rating_periods` + `invoices` + `credit_notes`
  (multi-document transaction, audit outside). `rating_periods` is U3's: see
  Waves.
- Cross-unit: reads `plans`/`subscriptions`/`tenants`/`codes` (U1),
  `usage_events`/`rating_periods` (U3), `customers`/`tenants` for the extract
  and the reconciliation report (U2, U1).

## U5 dunning (wave 2)

Owns `dunning_attempts`, `notifications`, `billing_audit_log`. Indexes
`uq_dunning_attempts_invoice_attempt`, `ix_dunning_attempts_scheduled`,
`uq_notifications_tenant_kind_sent`; `billing_audit_log` has none.

- Logic: `PKG_DUNNING` (`fn_overdue_accounts`, `sp_schedule_dunning`,
  `sp_suspend_overdue`; `services/legacy-billing/app/backends/oracle.py:122-133`).
- Both scheduler jobs (`services/legacy-billing/db/oracle/schema/04_jobs.sql:11`,
  `services/legacy-billing/db/oracle/schema/04_jobs.sql:22`):
  `JOB_NIGHTLY_DUNNING` (02:00 `schedule_dunning` + `suspend_overdue`) becomes a
  scheduled job in the billing service, created disabled like the estate's;
  `JOB_PURGE_AUDIT_LOG` retires with no replacement under the applied
  `d-audit-retention = match-live` (no TTL index, no purge; the `ttl-90d`
  alternative in `census/buckets.json` is the human's, not taken). Retired
  with it: `SEQ_BILLING_AUDIT_LOG`, `TRG_BILLING_AUDIT_LOG_ID`.
- Code: `GET /admin/overdue`, `GET /admin/dunning`
  (`services/legacy-billing/app/facade.py:304-354`); the legacy
  `/api/dunning/overdue`, `/api/dunning/schedule`, `/api/dunning/suspend`
  (`services/legacy-billing/app/app.py:81-95`).
- Atomic units: `schedule_dunning` = single-document inserts;
  `suspend_overdue` = one transaction per tenant over `tenants` +
  `subscriptions` + `subscriptions_hist` (U1, wave 1) + `notifications`.
- Cross-unit: reads `invoices` (U4, see Waves); `billing_audit_log` is written
  by every module through the U1 helper; U5 owns its load (0 live rows), recon
  and retention.

## Open human decisions (called out, not resolved here)

| decision | where it may add work | what changes if taken |
|----------|-----------------------|-----------------------|
| `bd-overdue-status-owner` (ticket alias d-overdue-owner) | **U5** | names who sets `invoices.statusCd = 40` after cutover; nobody in the app does today (spec `incompatibilities.behavior_differences`). If a service job or route is chosen it lands in U5 next to the nightly job; the deferred `ix_invoice_feed_status_due` ("overdue by due date") stays deferred until then. |
| `d-cdc-connector` | cutover: UNT-23 (`s5.1-delta-sync`) | names the off-repo CDC principal that writes the Oracle -> Atlas delta after each unit's initial load. No unit's scope depends on it; it may add connector configuration to the delta-sync ticket. |
| `d-mainframe-load` | cutover: UNT-23 / UNT-27 (`s6.3-repoint`) | names the post-cutover loader of `invoice_feed` / `invoice_feed_quarantine`. U4 fixes their shape and loads the census rows once; the recurring CUSTBILL month-end load is not in U4. |

Nothing above changes the wave plan; each is a scope note for the manager.

## Per-unit verification obligations (not proven by this ticket)

This ticket derives the model; it loads nothing and proves no parity. Each
unit PR owes: `python3 migration/billing/mapping/build_mapping_spec.py --check`
and `python3 migration/billing/units/check.py` still green; parity for its
entrypoints via `procs/harness` (`procs/oracle/oracle_map.yaml`); a green
`make tp-smoke`; and a live recon report under
`docs/tech-partnerships/contracts/schema/recon-report.schema.json` against
`ow_tp_billing_20261001T233613Z` - the fixture result is never merge evidence.
Cross-unit keys (`GET /me.customer`, `issue_invoice` -> `rating_periods`, U5 over
`invoices`) are verified at the wave gate (UNT-16, UNT-22), not per unit.

## Evidence

```sh
python3 migration/billing/units/check.py            # partition + cites + waves
python3 migration/billing/mapping/build_mapping_spec.py --check
python3 migration/billing/access_patterns/check.py
```
