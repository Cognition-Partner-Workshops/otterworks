# Wave 2 readiness (plan step `s4.2.0-preflight`, UNT-17)

Run branch `tp-run/mongodb-20261001T233613Z`, checked at `17ccb2e5` (merge of
#1783). Wave 1 is merged there (U1 backend/loader/fixture #1782, verification
#1783, recon anomaly scoping #1781, `histDate` fix #1784). Wave 2 is the four
units **U2 customers, U3 rating, U4 invoicing, U5 dunning**
(`migration/billing/units.md`, `units/units.json#waves[1]`), dispatched
together (`d-wave-width` = 4) as batch tickets UNT-18, UNT-19, UNT-20, UNT-21
(`s4.2.b01..b04`); verify ticket UNT-22 (`s4.2.verify`). This document is the
checklist the manager ticks gate `g-preflight-2` from. It loads nothing and
writes nothing: Atlas was read (list + count) only, Oracle was not touched.

Each batch worker reads its own section first, then "Common acceptance".

## 0. Write targets are disjoint and complete

`python3 migration/billing/waves/wave2/check_disjoint.py` reads only
`units/units.json` and `mapping_spec.json` and exits non-zero unless the four
write-target sets are pairwise disjoint, disjoint from U1's five collections,
and together exactly the 11 non-U1 collections of the spec; it checks the same
partition for the 14 source tables behind them (primary + embedded), the index
total (21 = 4 + 4 + 2 + 8 + 3) and the `billing_audit_log` rule below.
Output, 2026-10-02 (`waves/wave2/check_disjoint.json`):

```
U2 UNT-18: ['customers', 'customers_hist'] (4 indexes) <- ['CUSTOMER_MASTER', 'CUSTOMER_MASTER_HIST', 'ENTITY_ATTR_VALUE']
U3 UNT-19: ['rating_periods', 'usage_events'] (2 indexes) <- ['RATING_PERIODS', 'RATING_RESULTS', 'USAGE_EVENTS']
U4 UNT-20: ['credit_notes', 'invoice_feed', 'invoice_feed_quarantine', 'invoices'] (8 indexes) <- ['CREDIT_NOTES', 'INVOICES', 'INVOICE_HEADER', 'INVOICE_LINE', 'INVOICE_LINES']
U5 UNT-21: ['billing_audit_log', 'dunning_attempts', 'notifications'] (3 indexes) <- ['BILLING_AUDIT_LOG', 'DUNNING_ATTEMPTS', 'NOTIFICATIONS']
U1 (wave 1): ['codes', 'plans', 'subscriptions', 'subscriptions_hist', 'tenants'] (4 indexes)
pairwise disjoint: True; disjoint from U1: True; covers 11/11 non-U1 collections: True; indexes 21/21
billing_audit_log: owner U5, writer shipped by U1; others append only through the shared writer
PASS
```

### The one shared write: `billing_audit_log`

Every module appends audit documents through the `log_msg` port that U1 shipped
(`PKG_OW_UTIL` helper in `backends/mongo.py`; `units.json#cross_unit` `"*" ->
U5`), as a single-document insert outside any session or transaction
(`mapping_spec.json#collections[billing_audit_log].writes.autonomous`). That
does not make the collection a write target of U1, U2, U3 or U4: **U5 alone
lists it, loads it (0 live rows, `census.json#tables.BILLING_AUDIT_LOG`), runs
recon on it and owns its retention.** No other batch may create the collection,
add an index to it, load rows into it or pass it to `--collections`. The script
encodes this: it fails if any unit other than U5 lists the collection, if the
`"*" -> U5` edge or U1's writer scaffolding is missing, if the spec declares an
index on it or a retention other than `match-live` (`d-audit-retention`: no TTL
index, no purge, `JOB_PURGE_AUDIT_LOG` retires with no replacement), or if the
write is not declared autonomous.

## 1. Merge order inside the wave (`d-wave2-coupling` = parallel-merge-order)

Build all four in parallel on the merged wave 1; **merge U3, then U4, then U5.
U2 is independent** and merges whenever green. Two rebases are mandatory
before a live recon, not after:

- **U4 rebases on the merged U3** before its live recon and parity run:
  `sp_issue_invoice` finalizes the rating period inside its own transaction
  (`PKG_INVOICING` -> `PKG_RATING`, `04_pkg_invoicing.sql:134`; spec
  `atomic_units.issue_invoice` writes `rating_periods`, a U3 collection). U4
  does not carry its own copy of the finalize step; it calls U3's.
- **U5 rebases on the merged U4** before its live recon and parity run:
  `overdue` / `schedule_dunning` / `suspend_overdue` read `invoices`, so U5's
  live recon and the dunning scenarios need U4's `invoices` loaded in
  `ow_tp_billing_20261001T233613Z`.

Cross-unit keys (`GET /me.customer`, `issue_invoice` -> `rating_periods`, U5
over `invoices`) are verified at the wave gate (UNT-22), not per unit.

## 2. Atlas is empty for U2 to U5 (read-only check)

`mongosh "$MONGODB_ATLAS_URI"` against `ow_tp_billing_20261001T233613Z`,
`getCollectionNames()` + `countDocuments({})` per collection, 2026-10-02. Only
the five U1 collections exist (loaded by UNT-15/16); all eleven wave 2 targets
are absent:

```
database: ow_tp_billing_20261001T233613Z
collections present: ["codes","plans","subscriptions","subscriptions_hist","tenants"]
U2 customers: absent
U2 customers_hist: absent
U3 usage_events: absent
U3 rating_periods: absent
U4 invoices: absent
U4 credit_notes: absent
U4 invoice_feed: absent
U4 invoice_feed_quarantine: absent
U5 dunning_attempts: absent
U5 notifications: absent
U5 billing_audit_log: absent
U1 (for reference): codes=32, tenants=69, plans=3, subscriptions=69, subscriptions_hist=0
principal: [{"user":"otterworks-app","db":"admin"}]
```

## 3. `recon.py` on the fixture, one run per unit's `--collections`

`migration/billing/waves/wave2/fixture_recon.py` is `wave1/fixture_recon.py`
with two changes: it accepts `--unit U2|U3|U4|U5`, and the synthetic source
keeps the embedded child tables the unit's collections read
(`ENTITY_ATTR_VALUE`, `RATING_RESULTS`, `INVOICE_LINES`, `INVOICE_LINE`), which
the wave 1 driver dropped because U1 has none. Same faithful copy of
`fixtures/demo.json` (seed `714559852`), same mongod fixture
(`make mongo-billing-up`, `127.0.0.1:27117`, never Atlas), same restriction:

```sh
make mongo-billing-up
for u in U2 U3 U4 U5; do
  uv run --no-project --with pymongo==4.10.1 --with jsonschema==4.25.1 --with rfc3339-validator==0.1.4 \
    python3 migration/billing/waves/wave2/fixture_recon.py --unit $u \
      --mongo-uri 'mongodb://127.0.0.1:27117/?directConnection=true'
  make tp-validate-recon FILE=migration/billing/waves/wave2/$u.fixture.recon.json
done
```

| unit | `--collections` | synthetic rows -> documents | checks | verdict | validate |
|---|---|---:|---:|---|---|
| U2 | `customers,customers_hist` | 33,338 -> 25,001 | 28 | pass | PASS |
| U3 | `usage_events,rating_periods` | 823 -> 820 | 20 | pass | PASS |
| U4 | `invoices,credit_notes,invoice_feed,invoice_feed_quarantine` | 168,763 -> 18,796 | 38 | pass | PASS |
| U5 | `dunning_attempts,notifications,billing_audit_log` | 2 -> 2 | 18 | pass | PASS |

Reports: `waves/wave2/U2.fixture.recon.json` .. `U5.fixture.recon.json`
(`run_mode: fixture`, `merge_evidence: false`, `wave_readiness.plan_step:
s4.2.0-preflight`). Every planted anomaly kind is evaluated by exactly one run
and listed under `unverified_paths` by the other three (the #1781 scoping):
`dirty_dates`, `malformed_csv_lists`, `eav_boolean_spellings` in U2's,
`orphaned_rows` (37 lines -> `invoice_feed_quarantine`) in U4's. Fixture
coverage of U5 is thin by construction (census: `DUNNING_ATTEMPTS` 1,
`NOTIFICATIONS` 1, `BILLING_AUDIT_LOG` 0 live rows); its real check is the live
recon after the U4 rebase. No recon bug surfaced; one wording nit for the
manager, not fixed here: `recon.py:966` labels census-delta tables outside the
run's `--collections` as "outside the mapping spec" when they are merely
outside the run.

**None of these reports is merge evidence.** Each batch owes a live report
(section 5).

## 4. Units: what each batch writes and ports

Target database `ow_tp_billing_20261001T233613Z` via `MONGODB_ATLAS_URI` (by
name). Collections, indexes and decisions from `mapping_spec.json#collections`;
live rows from `census.json#tables`; code, routes, logic and retirements from
`units/units.json#units`. Money is Decimal128, never double; Oracle `DATE`
becomes a BSON UTC datetime; verbatim text dates keep the text with a derived
typed sibling only when it parses (`histDate` pattern, #1784).

### UNT-18, U2 customers (`s4.2.b01`)

| collection | source tables | live rows | decision | secondary indexes |
|---|---|---:|---|---|
| `customers` | `CUSTOMER_MASTER` + `ENTITY_ATTR_VALUE` as `attributes[]` | 25,000 + 8,333 | `d-flat-customer-columns`, `d-customer-eav` | `ix_customers_tenant_seq` `{tenantId: 1, custSeqNo: 1}`; `ix_customers_conversion_batch` `{conversionBatchNo: 1}`; `uq_customers_attributes_eav_id` `{attributes.eavId: 1}` unique, partial `$exists` |
| `customers_hist` | `CUSTOMER_MASTER_HIST` | 0 | `d-history-tables` | `ix_customers_hist_cust` `{custId: 1, _id: 1}` |

- Routes: `GET /api/v1/billing/customer` (`facade.py:277-303`, facade-side SQL,
  no PL/SQL entrypoint) and the `customer` sub-document of
  `GET /api/v1/billing/me` (route stays in U1; U2 fills the key that is null
  on the Mongo backend today).
- Logic: `TRG_CUSTOMER_MASTER_SEQ` keeps its derivation part (`custNameUpper`,
  `rowVersionNo` default); `TRG_CUSTOMER_MASTER_HIST` becomes the pre-image
  copy in the same transaction as any future customer update (no app write
  path exists today; loads are bulk). Retired: `SEQ_CUSTOMER_MASTER`,
  `SEQ_CUSTOMER_MASTER_HIST`, `SEQ_ENTITY_ATTR_VALUE`, `TRG_ENTITY_ATTR_VALUE_SEQ`.
- Fixture anomaly kinds owned: `dirty_dates` (50 `SIGNUP_DT` values that are
  not valid `DD-MON-YY` under RR: verbatim text kept, typed sibling only when
  it parses), `malformed_csv_lists` (31 `RELATED_ACCT_IDS`: verbatim text, no
  split that loses tokens), `eav_boolean_spellings` (`attributes[].value`
  verbatim; the typed `attributes[].typed` is loader-defined and recon checks
  only the verbatim field).
- Read by U4 (CUSTBILL extract, `BALANCES_SQL` grouped on
  `conversionBatchNo`); reads U1 `codes`. No atomic unit.
- Loader: the embedded `attributes[]` is the first collection the U1 loader
  refuses (`oracle_to_mongo.py` `_collection_maps` rejects embedded children);
  U2 extends it for one embedded child table, keeping `load_documents` in
  `recon.py` as the reference shape.

### UNT-19, U3 usage and rating (`s4.2.b02`)

| collection | source tables | live rows | decision | secondary indexes |
|---|---|---:|---|---|
| `usage_events` | `USAGE_EVENTS` | 814 | `d-reference-usage-events` | `ix_usage_events_tenant_occurred` `{tenantId: 1, occurredAt: -1, _id: -1}` |
| `rating_periods` | `RATING_PERIODS` + `RATING_RESULTS` as `result` | 3 + 3 | `d-embed-rating-result` | `uq_rating_periods_tenant_start` `{tenantId: 1, periodStart: 1}` unique |

- Routes: `GET /api/v1/billing/usage`, `POST /internal/usage/events`
  (`facade.py:196-229`, `355-400`); legacy `POST /api/rating/preview`,
  `POST /api/rating/finalize` (`app.py:44-55`); the usage bridge
  (`bridge/bridge.py:19-20`, SQS -> `/internal/usage/events`) keeps posting
  and the Mongo path inserts one `usage_events` document after the U1
  `ensure_tenant` bootstrap.
- Logic: `PKG_RATING` (`fn_usage_rating`, `fn_usage_summary`,
  `sp_finalize_rating`; entrypoints `usage_rating`, `usage_summary`,
  `finalize_rating`); package-global rating state between compute and finalize
  becomes per-request state. `TRG_USAGE_EVENTS_CHECK` (units > 0, `kindCd` in
  `codes` `USAGE_KIND`) becomes service/schema validation. Nothing retires.
- Atomic unit `finalize_rating` = one `rating_periods` document (header +
  `result`), atomic by construction.
- Fixture anomaly kinds owned: none (all four are listed as unverified in its
  report, which is correct).
- Written by U4's `issue_invoice` (`rating_periods`): **U3 merges first.**
- Loader: `rating_periods.result` is an embedded child; same loader extension
  as U2.

### UNT-20, U4 invoicing (`s4.2.b03`)

| collection | source tables | live rows | decision | secondary indexes |
|---|---|---:|---|---|
| `invoices` | `INVOICES` + `INVOICE_LINES` as `lines[]` | 3 + 2 | `d-embed-invoice-lines` | `ix_invoices_tenant_issued` `{tenantId: 1, issuedAt: -1, _id: -1}`; `ix_invoices_status_issued` `{statusCd: 1, issuedAt: 1, _id: 1}`; `uq_invoices_lines_id` `{lines.id: 1}` unique, partial |
| `credit_notes` | `CREDIT_NOTES` | 5 | | `ix_credit_notes_tenant_issued` `{tenantId: 1, issuedOn: 1, _id: 1}` |
| `invoice_feed` | `INVOICE_HEADER` + matched `INVOICE_LINE` as `lines[]` | 18,750 + 149,963 | `d-feed-embed-lines` | `ix_invoice_feed_batch` `{batchNo: 1}`; `uq_invoice_feed_lines_line_id` `{lines.lineId: 1}` unique, partial; `ix_invoice_feed_status_due` `{statusCd: 1, dueDate: 1}` **build deferred** (no reader until `bd-overdue-status-owner`) |
| `invoice_feed_quarantine` | orphan `INVOICE_LINE` (no header) | 37 | `d-feed-embed-lines` | `ix_invoice_feed_quarantine_invoice` `{invoiceId: 1}` |

- Routes: `GET /api/v1/billing/invoices`,
  `GET /api/v1/billing/invoices/<invoice_id>/lines` (`facade.py:230-276`);
  legacy `GET /api/invoices/<tenant_id>/preview`,
  `POST /api/invoices/<tenant_id>/issue`, `GET /api/invoices/<invoice_id>/lines`
  (`app.py:57-79`); admin reports `GET /api/v1/billing/admin/reports/{month-end,
  reconciliation,finance}` and legacy `GET /api/reports/{month-end,
  reconciliation,finance}` (`reports.py:159-286`).
- Logic: `PKG_INVOICING` (`fn_invoice_preview`, `fn_invoice_lines`,
  `sp_issue_invoice`; entrypoints `invoice_preview`, `issue_invoice`,
  `invoice_lines`). `issue_invoice` is the multi-document transaction
  `rating_periods` + `invoices` + `credit_notes` (audit append outside it);
  the finalize step is U3's. `reports.py` `STATUS_SQL`/`LINE_SQL`/`BALANCES_SQL`
  move to `invoice_feed` / `customers` aggregations and `reconciliation`
  returns pass|fail with per-check results instead of `status: baseline`;
  `finance` keeps reading the published CSV. CUSTBILL extract
  (`make tp-month-end`, `etl/legacy-extra/tools/oracle_custbill_extract.py`)
  reads `invoice_feed` + `customers` + `tenants` on the Mongo backend; the
  ksh/Perl chain after it is unchanged. Nothing retires.
- Fixture anomaly kinds owned: `orphaned_rows` (37 `INVOICE_LINE` rows whose
  `INVOICE_ID` has no header, `INVOICE_NO` `<NS>-GHOST-<n>`) -> one
  `invoice_feed_quarantine` document each; `quarantine.capturedAt` and the
  `quarantine` object are loader-defined and outside recon.
- Writes U3's `rating_periods` through `issue_invoice`; reads U2's `customers`
  and U1's `plans`/`subscriptions`/`tenants`/`codes`. **Rebase on the merged
  U3 before the live recon.** `statusCd` 40/30 is never written by the app
  (`bd-overdue-status-owner` is open and belongs to U5): U4 does not add an
  overdue writer.
- Loader: `invoices.lines[]`, `invoice_feed.lines[]` (embedded) and
  `invoice_feed_quarantine` (quarantine of `invoice_feed`; a header arriving
  later moves the rows into `invoice_feed.lines` in one transaction) are all
  rejected by the U1 loader today; U4 extends it for embedded + quarantine.
  The recurring post-cutover feed load is `d-mainframe-load` (cutover), not U4.

### UNT-21, U5 dunning and audit (`s4.2.b04`)

| collection | source tables | live rows | decision | secondary indexes |
|---|---|---:|---|---|
| `dunning_attempts` | `DUNNING_ATTEMPTS` | 1 | | `uq_dunning_attempts_invoice_attempt` `{invoiceId: 1, attemptNo: 1}` unique; `ix_dunning_attempts_scheduled` `{scheduledFor: -1, _id: -1}` |
| `notifications` | `NOTIFICATIONS` | 1 | | `uq_notifications_tenant_kind_sent` `{tenantId: 1, kindCd: 1, sentAt: 1}` unique |
| `billing_audit_log` | `BILLING_AUDIT_LOG` | 0 | `d-audit-retention` = match-live | **none** (no TTL index) |

- Routes: `GET /api/v1/billing/admin/overdue`, `GET /api/v1/billing/admin/dunning`
  (`facade.py:304-354`); legacy `GET /api/dunning/overdue`,
  `POST /api/dunning/schedule`, `POST /api/dunning/suspend` (`app.py:81-95`).
- Logic: `PKG_DUNNING` (`fn_overdue_accounts`, `sp_schedule_dunning`,
  `sp_suspend_overdue`; entrypoints `overdue`, `schedule_dunning`,
  `suspend_overdue`). `JOB_NIGHTLY_DUNNING` (02:00 `schedule_dunning` +
  `suspend_overdue`) becomes a scheduled job in the billing service, created
  disabled like the estate's. Retired: `JOB_PURGE_AUDIT_LOG` (no replacement
  under match-live), `SEQ_BILLING_AUDIT_LOG`, `TRG_BILLING_AUDIT_LOG_ID`.
- Atomic units: `schedule_dunning` = single-document inserts (unique key
  refuses the `attemptNo` race); `suspend_overdue` = one transaction per tenant
  over U1's `tenants` + `subscriptions` + `subscriptions_hist` + `notifications`.
- `billing_audit_log`: U5 loads the 0 live rows, runs recon on the collection
  (every row compared, no age cut-off) and owns retention. The writer is U1's
  shared `log_msg` port; U5 changes neither the helper nor its callers, and
  adds no index to the collection.
- **`d-overdue-owner` = external-repointed: U5 does not mark invoices overdue.**
  `fn_overdue_accounts` keeps reading `invoices.statusCd = 40` as today
  (`ix_invoices_status_issued`, a U4 index); who sets 40/30 after cutover is
  `bd-overdue-status-owner`, repointed outside this wave. `ix_invoice_feed_status_due`
  stays deferred.
- Fixture anomaly kinds owned: none.
- Reads U4's `invoices`: **rebase on the merged U4 before the live recon**;
  the live recon of `dunning_attempts` is only meaningful with U4's invoices
  present.
- Loader: three primary-table collections, so the U1 loader handles them
  as-is (`--collections dunning_attempts,notifications,billing_audit_log`).

## 5. Common acceptance (what the manager merges each batch on)

1. One PR into `tp-run/mongodb-20261001T233613Z` (never `tech-partnerships`
   or `main`), review budget 2 rounds, `make tp-smoke` green on both
   `BILLING_BACKEND=oracle` and `mongo` (`mongo:7` fixture, never Atlas).
   Writes only the unit's collections from section 0; `check_disjoint.py`
   still PASS if `units.json` or `mapping_spec.json` changed (they should not
   without a plan decision).
2. Loader under `migration/billing/loaders/`: reuse `oracle_to_mongo.py` or
   extend it (embedded children for U2/U3/U4, quarantine for U4) rather than
   adding a second loader; python-oracledb read under `SET TRANSACTION READ
   ONLY` from `OW_TP_ORACLE_RO_DSN`, pymongo upsert on `_id` into
   `ow_tp_billing_20261001T233613Z` only, `--passes 2` proving the rerun is a
   no-op, documents identical to `recon.load_documents`, the unit's indexes
   from section 4 (and only those; `ix_invoice_feed_status_due` is not built).
3. A **live** recon report committed under `migration/billing/recon/out/` (or
   the unit's own directory), produced by `recon.py run --mode live
   --collections <the unit's list from section 3>` against
   `OW_TP_ORACLE_RO_DSN` and `MONGODB_ATLAS_URI`, that validates with
   `make tp-validate-recon FILE=<report>` and passes under `tolerances.json`:
   `run_mode: live`, `verdict: pass`, `merge_evidence: true`,
   `idempotency_rerun.result: pass`. U4 runs it after rebasing on merged U3;
   U5 after rebasing on merged U4. The fixture reports in `waves/wave2/` are
   never merge evidence.
4. Route parity, `BILLING_BACKEND=oracle` vs `mongo`, for the unit's
   entrypoints via `procs/harness` against the immutable transcripts
   (`make procs-parity MODULE=<module>` or the facade routes): U3 `rating`
   `001-008`, U4 `invoicing` `001-006`, U5 `dunning` `001-005`
   (`procs/scenarios/<module>/`, `procs/transcripts/<module>/`). U2 has no
   PL/SQL entrypoint: parity is `GET /api/v1/billing/customer` and the
   `customer` key of `GET /api/v1/billing/me` field-for-field on both
   backends. U4 additionally: the three admin report pairs and
   `make tp-month-end` on the Mongo backend produce the same output as on
   Oracle.
5. `python3 migration/billing/units/check.py` and
   `python3 migration/billing/mapping/build_mapping_spec.py --check` still
   green; no change to `tolerances.json`, `mapping_spec.json` or
   `units/units.json` without a plan decision. Oracle `OW_BILLING` stays
   read-only (no writes, grants or DDL).
