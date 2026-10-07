# 01 — Census cross-check: live catalog vs DDL (plan step `s2.1-census`)

Run branch `tp-run/mongodb-20261007T161014Z`, plugin `mongo-migration-plugin` @ `353280fc837193a40ccc005cb62fb4ffaf8ac16f`
(skill `schema-modeling`, scripts unpatched). Source: local Oracle Free fixture, schema `OW_BILLING`, after the
`mmprt` mini seed and one package exercise (UNT8-2). This document records; it reconciles nothing and the estate
(`services/legacy-billing/db/oracle/`) was not edited.

| artifact | producer | contract | counts |
|---|---|---|---|
| `.migration/census.json` | `catalog_census.py --family oracle --source-dsn-secret MMP_RT_SRC_DSN --schema OW_BILLING --count-rows --statement-timeout 300` | `census_version: 2`, `mode: live_catalog`, `validate()` → no errors | tables 20, columns 434, FKs 13, triggers 7, PL/SQL units 10, sequences 5, scheduler jobs 2, traps 37, findings 19, unparsed 0 |
| `.migration/census_ddl.json` | `ddl_census.py --dialect oracle` over `schema/01_tables.sql 02_horror.sql 03_seed_static.sql 04_upgrade_static.sql 04_jobs.sql` | `census_version: 2`, `mode: offline_ddl`, `validate()` → no errors | tables 19, columns 431, FKs 13, triggers 7, PL/SQL units 0, sequences 5, scheduler jobs 2, traps 42, findings 5, unparsed 2 |
| `.migration/census_diff.json` | `census_diff.py census.json census_ddl.json --json` (exit 1 = differences) | — | 1 item |

Live catalog inputs (all `origin: live`, one connection, read-only): tables 20 rows, columns 434, constraints 44,
indexes 31, plsql_objects 17, triggers 7, sequences 5, rowid_usage 0, scheduler_jobs 2.

## 1. `census_diff.json` — every item

| # | kind | object | live (a) | DDL (b) | reading |
|---|---|---|---|---|---|
| 1 | `table` | `FIXTURE_META` | present (3 columns: `MARKER VARCHAR2`, `VALUE VARCHAR2`, `INITIALIZED_AT TIMESTAMP`; no PK; 2 rows) | absent | Not created by any of the five census inputs. `04_upgrade_static.sql` only touches it: the `DECLARE … EXECUTE IMMEDIATE 'ALTER TABLE fixture_meta ADD (marker, value)'` block at line 6 and the `MERGE INTO fixture_meta` at line 170 — both of which `ddl_census.py` reports as unparsed (§3), so even the two added columns are invisible offline. `CREATE TABLE fixture_meta` lives in `services/legacy-billing/db/oracle/startup/00_init.sh:150` (container init, outside the schema scripts): fixture bookkeeping, not a billing object. Recorded; not a migration unit. |

That is the only structural difference `census_diff.py` reports: the 19 shared tables agree on columns (name,
type, length, precision, scale, nullable), primary keys (19 on each side), unique sets (6 each), foreign keys (13
each, same columns/ref/on_delete), sequence names (5) and trigger name+table (7). `census_diff.py` compares the
model only; the sections below record the differences it ignores by design.

## 2. Findings emitted by the tools — verbatim, none silenced

### 2.1 `catalog_census.py` (live) — 19 findings

| kind | object(s) |
|---|---|
| `no_primary_key` | table `FIXTURE_META` |
| `plsql_unit_needs_manual_review` | `PACKAGE PKG_OW_UTIL`, `PACKAGE BODY PKG_OW_UTIL` |
| `plsql_unit_needs_manual_review` | `PACKAGE PKG_PLANS`, `PACKAGE BODY PKG_PLANS` |
| `plsql_unit_needs_manual_review` | `PACKAGE PKG_RATING`, `PACKAGE BODY PKG_RATING` |
| `plsql_unit_needs_manual_review` | `PACKAGE PKG_INVOICING`, `PACKAGE BODY PKG_INVOICING` |
| `plsql_unit_needs_manual_review` | `PACKAGE PKG_DUNNING`, `PACKAGE BODY PKG_DUNNING` |
| `trigger_business_logic` | `TRG_BILLING_AUDIT_LOG_ID` on `BILLING_AUDIT_LOG` |
| `trigger_business_logic` | `TRG_SUBSCRIPTIONS_HIST` on `SUBSCRIPTIONS` |
| `trigger_business_logic` | `TRG_SUB_NO_UNCANCEL` on `SUBSCRIPTIONS` |
| `trigger_business_logic` | `TRG_USAGE_EVENTS_CHECK` on `USAGE_EVENTS` |
| `trigger_business_logic` | `TRG_CUSTOMER_MASTER_SEQ` on `CUSTOMER_MASTER` |
| `trigger_business_logic` | `TRG_CUSTOMER_MASTER_HIST` on `CUSTOMER_MASTER` |
| `trigger_business_logic` | `TRG_ENTITY_ATTR_VALUE_SEQ` on `ENTITY_ATTR_VALUE` |
| `row_estimate_counted` | basis `count(*)`, all 20 tables: RATING_PERIODS, CUSTOMER_MASTER_HIST, INVOICES, CREDIT_NOTES, CODES, TENANTS, PLANS, SUBSCRIPTIONS, USAGE_EVENTS, DUNNING_ATTEMPTS, NOTIFICATIONS, INVOICE_LINES, CUSTOMER_MASTER, ENTITY_ATTR_VALUE, FIXTURE_META, INVOICE_HEADER, INVOICE_LINE, BILLING_AUDIT_LOG, SUBSCRIPTIONS_HIST, RATING_RESULTS |

No `catalog_query_empty`, `visibility` or `row_estimate_missing` finding was emitted (`--count-rows` replaced
`num_rows` with `COUNT(*)` for every table, hence the single `row_estimate_counted`).

### 2.2 `ddl_census.py` (offline) — 5 findings

| kind | object | evidence (verbatim) |
|---|---|---|
| `reference_data_candidate` | `ENTITY_ATTR_VALUE` | "8 seed rows, no FKs on this table; cannot distinguish lookup from entity" |
| `trigger_business_logic` | `TRG_SUBSCRIPTIONS_HIST` on `SUBSCRIPTIONS` | — |
| `trigger_business_logic` | `TRG_SUB_NO_UNCANCEL` on `SUBSCRIPTIONS` | — |
| `trigger_business_logic` | `TRG_USAGE_EVENTS_CHECK` on `USAGE_EVENTS` | — |
| `trigger_business_logic` | `TRG_CUSTOMER_MASTER_HIST` on `CUSTOMER_MASTER` | — |

Reading: the live census flags all 7 triggers as business logic; the DDL census flags 4 and instead classifies the
three `*_SEQ` / `*_ID` triggers as the `sequence_trigger_identity` trap (§4). Same objects, different bucket per
producer; both retained.

## 3. `ddl_census.py` unsupported / unparsed syntax — by file and line, verbatim prefix

| file | line | statement (as reported) |
|---|---|---|
| `services/legacy-billing/db/oracle/schema/04_upgrade_static.sql` | 6 | `DECLARE marker_columns NUMBER; BEGIN SELECT COUNT(*) INTO marker_columns FROM user_tab_columns WHERE table_name = 'FIXTURE_META' AND column_name = 'MARKER'; IF marker_columns = 0 THEN EXECUTE IMMEDIAT…` |
| `services/legacy-billing/db/oracle/schema/04_upgrade_static.sql` | 170 | `MERGE INTO fixture_meta target USING (SELECT 'static_seed_version' AS marker, '2' AS value FROM dual) source ON (target.marker = source.marker) WHEN MATCHED THEN UPDATE SET target.value = source.value` |

Both are anonymous-block / DML on `FIXTURE_META` (the §1 diff item). Nothing in `01_tables.sql`, `02_horror.sql`,
`03_seed_static.sql` or `04_jobs.sql` was reported unparsed. Not fixed: the estate is read-only.

## 4. Differences `census_diff.py` ignores by design (recorded for later steps)

| area | live | DDL | reading |
|---|---|---|---|
| `plsql_units` | 10 (5 packages × spec+body: `PKG_OW_UTIL`, `PKG_PLANS`, `PKG_RATING`, `PKG_INVOICING`, `PKG_DUNNING`) | 0 | The packages live in `services/legacy-billing/db/oracle/packages/01..05_pkg_*.sql`, which the ticket's five-file input list does not include. Not a parser gap; an input-scope difference. |
| `row_estimate` | `COUNT(*)` per table (see fixture manifest) | `null` everywhere | Contract behaviour of `offline_ddl`. |
| `seed_rows` | `{}` | 14 tables from `03_seed_static.sql` / `04_upgrade_static.sql` (CODES 32, TENANTS 11, PLANS 3, SUBSCRIPTIONS 11, USAGE_EVENTS 16, RATING_PERIODS 3, RATING_RESULTS 3, INVOICES 5, CREDIT_NOTES 5, DUNNING_ATTEMPTS 1, NOTIFICATIONS 1, INVOICE_LINES 6, CUSTOMER_MASTER 2, ENTITY_ATTR_VALUE 8) | Live counts exceed the static seed where the `mmprt` mini seed and the package exercise added rows (e.g. TENANTS 15 vs 11 static seed rows, CUSTOMER_MASTER 201 vs 2, ENTITY_ATTR_VALUE 70 vs 8); CODES is 32 on both sides (reference data, untouched). |
| `traps` | 37 | 42 | Identical 37 `(kind, table, column)` triples on both sides; DDL adds 5 that need seed/DDL text: `reference_data` on `CODES`, `seeded_table` on `CUSTOMER_MASTER`, `sequence_trigger_identity` on `BILLING_AUDIT_LOG`, `CUSTOMER_MASTER`, `ENTITY_ATTR_VALUE`. |
| `indexes` | 0 (catalog returned 31 index rows) | 0 | Both producers fold PK/unique indexes into `primary_key` / `unique` and emit no standalone `indexes[]` entry; the live catalog's 31 rows are all constraint-backed. Nothing lost, but the index plan step gets no non-constraint indexes from either census. |
| `columns` | 434 | 431 | Exactly the 3 `FIXTURE_META` columns. |
| `relationships` | 13, `cardinality_basis: assumed` | 13 | Derived from the same 13 FKs. |
| `views` / `materialized_views` | none | none | — |

## 5. Bucket check — every source object in exactly one bucket

| bucket | live | DDL | objects |
|---|---|---|---|
| `tables` | 20 | 19 | CODES, TENANTS, PLANS, SUBSCRIPTIONS, USAGE_EVENTS, RATING_PERIODS, RATING_RESULTS, INVOICES, INVOICE_LINES, CREDIT_NOTES, DUNNING_ATTEMPTS, NOTIFICATIONS, BILLING_AUDIT_LOG, SUBSCRIPTIONS_HIST, CUSTOMER_MASTER, CUSTOMER_MASTER_HIST, ENTITY_ATTR_VALUE, INVOICE_HEADER, INVOICE_LINE (+ FIXTURE_META live only) |
| `sequences` | 5 | 5 | SEQ_BILLING_AUDIT_LOG, SEQ_SUBSCRIPTIONS_HIST, SEQ_CUSTOMER_MASTER, SEQ_CUSTOMER_MASTER_HIST, SEQ_ENTITY_ATTR_VALUE |
| `triggers` | 7 | 7 | TRG_BILLING_AUDIT_LOG_ID, TRG_SUBSCRIPTIONS_HIST, TRG_SUB_NO_UNCANCEL, TRG_USAGE_EVENTS_CHECK, TRG_CUSTOMER_MASTER_SEQ, TRG_CUSTOMER_MASTER_HIST, TRG_ENTITY_ATTR_VALUE_SEQ (all `enabled: true`) |
| `plsql_units` | 10 | 0 | 5 package specs + 5 bodies (see §4) |
| `scheduler_jobs` | 2 | 2 | JOB_NIGHTLY_DUNNING (`FREQ=DAILY;BYHOUR=2;BYMINUTE=0`), JOB_PURGE_AUDIT_LOG (`FREQ=DAILY;BYHOUR=3;BYMINUTE=30`) |

Live `plsql_objects` query returned 17 rows = 10 package units + 7 triggers; every row is bucketed. Both `_HIST`
tables are in `tables`. **Unbucketed objects: none** on either side.

## 6. Row counts of note (live, `COUNT(*)`, post package exercise)

`SUBSCRIPTIONS_HIST` 6, `BILLING_AUDIT_LOG` 73 — non-zero as required. `CUSTOMER_MASTER_HIST` **0**: no package,
job or ops path updates `CUSTOMER_MASTER`, so `TRG_CUSTOMER_MASTER_HIST` never fired; left at 0 by manager decision
(UNT8-2, no direct DML) — it will grade UNVERIFIED and is a §4/§5 finding, not a census defect. Full counts are in
`.migration/fixtures/mmprt-mini.json`.
