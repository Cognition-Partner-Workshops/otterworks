# 05 — Design decisions (UNT9, s3.1-design-decisions)

| Run | Value |
|---|---|
| Run branch | `tp-run/mongodb-20261008T120222Z` |
| Plugin | `349cb2d17dccb246409e7750657e25843bf53be8` (unpatched) |
| Mapping | `map-v2` — `.migration/mapping_spec.json` sha256 `ccd1078bedc904709411112483a873f04287748711713a1c3af03ddd0231512c` (`model_patch.py --check` exit 0, 83 decisions); supersedes `map-v1` sha256 `a0e184e2ade23705188ea91766e2b1095091c94b938e45cdc9543fdd6ea20752` after the UNT9-12 round-1 correction (b.1/b.7 below) |
| Input | `map-draft-2` proposal `.migration/mapping_spec.proposed.json`: 30 `modeling.unresolved`, 50 collection `open_questions`, 0 `child_open_questions`, `known_incompatibilities` key absent |
| Decisions file | `.migration/design_decisions.json` — 83 entries (67 resolve, 10 date_format, 2 pattern, 1 set_key, 1 note); every entry cites `file:line` under `services/legacy-billing/db/oracle/` or `source: customer` |
| Tolerances | `tol-1` — `.migration/recon_tolerances.json` sha256 `a23d517a8e6d00c84f668c0016ef0e42b16625d45ab7e4166e3838abf241e3da` (untouched) |
| Target | Atlas database `mmp_rt_b5_oracle` only |

## (a) Proposer decisions on the named shapes (accepted as-is)

| Shape | Proposer decision / rule | Evidence cited by the proposer | Note |
|---|---|---|---|
| CUSTOMER_MASTER | own collection `customerMaster`, key `CUST_ID`, no references; `TENANT_ID` is an unenforced pointer (`pointer_resolve`: 200/201 unresolved) | DDL `schema/02_horror.sql:22`, data profile; `access_basis: ddl_only` (no runtime caller) | kept as reference by name; orphans preserved |
| CUSTOMER_MASTER → INVOICE_HEADER → INVOICE_LINE | three collections, `reference` on each unenforced edge (`INVOICE_HEADER.CUST_ID`, `INVOICE_LINE.INVOICE_ID`, `INVOICE_LINE.CUST_ID`), no embed (no FK, no access evidence) | DDL `schema/02_horror.sql:401-440` ("no FKs"), `pointer_resolve`: `INVOICE_LINE.INVOICE_ID` 37/1500 unresolved = the 37 planted orphans; `TENANT_ID` 0 % resolve on both | orphans loaded as-is, recon by exact row count |
| ENTITY_ATTR_VALUE | own collection `entityAttrValue`, pattern annotation `eav` (polymorphic `ENTITY_TYPE`, so no attribute-embed into one parent) | DDL `schema/02_horror.sql:376-385`, `value_domain:ENTITY_ATTR_VALUE.ENTITY_TYPE` | — |
| `_HIST` trigger tables | `customerMasterHist`, `subscriptionsHist`: pattern `history_copy` ("separate versions collection keyed by history id; do not embed unbounded history") | census trap; triggers `schema/02_horror.sql:358`, `schema/01_tables.sql:206` | — |
| CODES lookups | `codes` own collection, key (`CODE_TYPE`,`CODE_VAL`), `access_basis: ddl_only`; 12 `code_lookup` questions on `*_CD` columns | DDL `schema/01_tables.sql:8-14`, `code_resolve:*` profile refs | reference data, codes kept numeric |
| SUBSCRIPTIONS_HIST | `history_copy` of SUBSCRIPTIONS, key `HIST_ID`; `HIST_DT` text (`%Y%m%d` measured, 0 % conformance to assumed) | `schema/01_tables.sql:190-192`, text_shapes profile | — |
| BILLING_AUDIT_LOG | own collection, key `LOG_ID`; purge job noted as `scheduler_job` | `schema/01_tables.sql:169`, `schema/04_jobs.sql:21-28` | TTL recorded as resolve (not a compiled pattern) |
| INVOICES ⊃ INVOICE_LINES | the single embed `invoices.lines` (1:N, basis `derived` from DDL + data) | FK + `LINE_NO` ordinal | unchanged |

Evidence flags observed in `.migration/access_patterns.json` (125 patterns):

| Flag | History / audit edges | Invoice edges | Any routine pattern |
|---|---|---|---|
| `txn` | yes — 1 of 10 hist/audit patterns (trigger-sourced `_HIST` writes carry none) | yes — 9 of 26 invoice-table patterns | 44 patterns total |
| `written_together` | no (field absent) | no (field absent) | no |
| `via_trigger` | no — trigger patterns carry a `trigger{on,events}` block instead | no | no |
| `via` (call graph) | — | — | yes, 1 pattern (`pkg_ow_util.log_msg` via `pkg_dunning.sp_schedule_dunning`) |
| `depth` (call graph) | — | — | yes, 14 routine patterns |
| `suggested_frequency` | — | — | yes, 91 of 125 patterns (from `.migration/workload.json`); the other 34 confirmed/rejected in UNT9-4 |
| `known_incompatibilities` | key absent from `data_profile.json` → blind spot (recorded as a `note` decision), not evidence of none | | |

## (b) Manual corrections (12; UNT8 needed 7)

| # | Op | Target | Why | Cite |
|---|---|---|---|---|
| 1-6 | `date_format` | `customerMasterHist` HIST_DT (`%d-%b-%y %H:%M:%S`), SIGNUP_DT, LAST_ACTIVITY_DT, LAST_INVOICE_DT, LAST_PAYMENT_DT, TERMINATE_DT (`%d-%b-%y`) | proposer assumed the format on an empty table; DDL and the trigger name it | `schema/02_horror.sql:372`, `:225-229` |
| 7-9 | `date_format` | `customerMaster` LAST_INVOICE_DT, LAST_PAYMENT_DT, TERMINATE_DT (`%d-%b-%y`) | `VARCHAR2(9)` DD-MON-YY text dates | `schema/02_horror.sql:65-67` |
| 1/7 (map-v2 edit-in-place) | `date_format` + `raw_field: signupDtRaw` | `customerMasterHist` SIGNUP_DT (existing entry edited) and `customerMaster` SIGNUP_DT (entry added — map-v1 relied on the proposer's `data_profile` format with no decision row); `unparseable → null` | w1-b01 live recon FAIL under map-v1: 41 CUSTOMER_MASTER.SIGNUP_DT values are not DD-MON-YY (`N/A`, `9/9/9999`, `99-99-999`, blanks, impossible DD-MON-YY) and the harness cannot PASS `unparseable: keep` on planted garbage; plan decision d-date-unparseable → raw_field; count stays 12 (correction, not a new shape) | `source: customer` — "planted horrors preserved, not repaired; exact parity" |
| 10 | `set_key` | `fixtureMeta` → `MARKER` (`nullable_ok`) | proposer had no comparison key (load-order only) | `schema/04_upgrade_static.sql:15` |
| 11 | `pattern extended_reference` | `invoices` ← TENANTS.`STATUS_CD` (join TENANT_ID = ID) | `fn_overdue_accounts` reads tenant status with every overdue invoice | `packages/05_pkg_dunning.sql:21-29` |
| 12 | `pattern extended_reference` | `subscriptions` ← PLANS.`CODE`,`TIER_CD`,`MONTHLY_FEE`,`INCLUDED_UNITS` (join PLAN_ID = ID) | `fn_entitlement` reads the plan fields with the covering subscription | `packages/02_pkg_plans.sql:53-68` |

Not corrected on purpose: TENANTS → SUBSCRIPTIONS extended-reference candidate (only `t.id` is read, `packages/02_pkg_plans.sql:61-63`); SUBSCRIPTIONS_HIST.HIST_DT (mixed formats — rule recorded as a resolve, no repair); repeating groups kept flat for column-level recon.

## (c) Open questions raised by the proposer and their disposition

| Kind | Count | Disposition | Cite kind |
|---|---|---|---|
| `date_format_assumed` (unresolved) | 10 | 9 closed by `date_format` (b.1-9); SUBSCRIPTIONS_HIST.HIST_DT resolved: try `DD-MON-YY HH24:MI:SS` then `YYYYMMDD`, keep raw when neither parses | file:line |
| `no_comparison_key` (unresolved) | 1 | FIXTURE_META `set_key` MARKER (b.10) | file:line |
| `plsql_unit_needs_manual_review` (unresolved) | 10 | logic ports to the billing service; access captured as routine patterns; no model change | file:line (package headers) |
| `trigger_business_logic` (unresolved) | 7 | sequence triggers → app assigns ids; `_HIST` triggers → app writes the history_copy doc in the same transaction; `TRG_SUB_NO_UNCANCEL`, `TRG_USAGE_EVENTS_CHECK` → app rule + schema validation | file:line (trigger DDL) |
| `scheduler_job` (unresolved) | 2 | JOB_NIGHTLY_DUNNING → billing-service scheduler (cold patterns); JOB_PURGE_AUDIT_LOG → TTL index on `billingAuditLog.loggedAt`, 90 d | file:line `schema/04_jobs.sql` |
| `no_access_evidence` | 10 | no runtime caller outside the intake register; keep as collection, indexes deferred to the index ticket | file:line / customer |
| `code_lookup` | 12 | keep numeric `*_CD`; `codes` stays reference data; DECODE stays in the app | file:line |
| `date_as_string` | 6 | 1 closed by the `date_format` ops (customerMasterHist); 5 resolved: family DD-MON-YY rule, raw kept when unparseable | file:line |
| `csv_list` | 3 | split to string arrays at load (max 3 elements measured); source string retained for recon | file:line |
| `unenforced_pointer` | 5 | reference by id; unresolved pointers loaded as-is | customer (planted orphans preserved) |
| `pointer_unresolved` | 4 | planted orphans / foreign tenant ids loaded as-is, reconciled by exact row count | customer |
| `pointer_target_suspect` | 2 | target stays TENANTS by name; 0 % resolve is the planted mainframe feed | file:line + customer |
| `extended_reference_candidate` | 3 | 2 applied (b.11-12); TENANTS→SUBSCRIPTIONS rejected (only key read) | file:line |
| `repeating_group` | 2 | keep numbered columns flat for parity recon; array folding deferred until a reader needs it | file:line |
| `polymorphic_pointer` | 1 | EAV stays its own collection keyed `eavId`, lookup (entityType, entityId, attrName) | file:line |
| `single_valued_index_key` | 1 | keep `activeYn` field, no index | file:line |
| `date_format_nonconforming` | 1 | CUSTOMER_MASTER.SIGNUP_DT keeps DD-MON-YY; 41 nonconforming rows (measured by recon, map-v2) keep the raw string in `signupDtRaw`, parsed field null — counted not repaired | customer |
| `child_open_questions` | 0 | none raised | — |
| `known_incompatibilities` | 0 hits (key absent) | blind spot recorded as `note` decision | profile |

Totals: 30 unresolved + 50 open_questions + 0 child + 1 incompat note = 81 dispositions, 82 decision entries (one `resolve` per item plus the two applied patterns); result `unresolved 0 / open_questions 0`.

## (d) Units and write targets
_placeholder — written by the record ticket_

## (e) Recon plan
_placeholder — written by the record ticket_

## (f) Rehearsal and evidence
_placeholder — written by the record ticket_
