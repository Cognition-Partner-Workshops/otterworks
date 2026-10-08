# 05 — Design decisions (UNT9; §a–§c s3.1-design-decisions, §d–§f s5.1-record)

| Run | Value |
|---|---|
| Run branch | `tp-run/mongodb-20261008T120222Z` |
| Plugin | `349cb2d17dccb246409e7750657e25843bf53be8` (unpatched) |
| Mapping | `map-v3` — `.migration/mapping_spec.json` sha256 `c158f8bb469d1e2733cfae5aa26e315d0ade4490f1164048ee161230c866dbd7` (`model_patch.py --check --census` exit 0, 84 decisions); supersedes `map-v2` sha256 `ccd1078bedc904709411112483a873f04287748711713a1c3af03ddd0231512c` (UNT9-10 round-1 correction b.13) and `map-v1` sha256 `a0e184e2ade23705188ea91766e2b1095091c94b938e45cdc9543fdd6ea20752` (UNT9-12 round-1 correction b.1/b.7) |
| Input | `map-draft-2` proposal `.migration/mapping_spec.proposed.json`: 30 `modeling.unresolved`, 50 collection `open_questions`, 0 `child_open_questions`, `known_incompatibilities` key absent |
| Decisions file | `.migration/design_decisions.json` — 84 entries (69 resolve, 11 date_format, 2 pattern, 1 set_key, 1 note); every entry cites `file:line` under `services/legacy-billing/db/oracle/` or `source: customer` |
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

## (b) Manual corrections (13; UNT8 needed 7)

| # | Op | Target | Why | Cite |
|---|---|---|---|---|
| 1-6 | `date_format` | `customerMasterHist` HIST_DT (`%d-%b-%y %H:%M:%S`), SIGNUP_DT, LAST_ACTIVITY_DT, LAST_INVOICE_DT, LAST_PAYMENT_DT, TERMINATE_DT (`%d-%b-%y`) | proposer assumed the format on an empty table; DDL and the trigger name it | `schema/02_horror.sql:372`, `:225-229` |
| 7-9 | `date_format` | `customerMaster` LAST_INVOICE_DT, LAST_PAYMENT_DT, TERMINATE_DT (`%d-%b-%y`) | `VARCHAR2(9)` DD-MON-YY text dates | `schema/02_horror.sql:65-67` |
| 1/7 (map-v2 edit-in-place) | `date_format` + `raw_field: signupDtRaw` | `customerMasterHist` SIGNUP_DT (existing entry edited) and `customerMaster` SIGNUP_DT (entry added — map-v1 relied on the proposer's `data_profile` format with no decision row); `unparseable → null` | w1-b01 live recon FAIL under map-v1: 41 CUSTOMER_MASTER.SIGNUP_DT values are not DD-MON-YY (`N/A`, `9/9/9999`, `99-99-999`, blanks, impossible DD-MON-YY) and the harness cannot PASS `unparseable: keep` on planted garbage; plan decision d-date-unparseable → raw_field; count stays 12 (correction, not a new shape) | `source: customer` — "planted horrors preserved, not repaired; exact parity" |
| 10 | `set_key` | `fixtureMeta` → `MARKER` (`nullable_ok`) | proposer had no comparison key (load-order only) | `schema/04_upgrade_static.sql:15` |
| 11 | `pattern extended_reference` | `invoices` ← TENANTS.`STATUS_CD` (join TENANT_ID = ID) | `fn_overdue_accounts` reads tenant status with every overdue invoice | `packages/05_pkg_dunning.sql:21-29` |
| 12 | `pattern extended_reference` | `subscriptions` ← PLANS.`CODE`,`TIER_CD`,`MONTHLY_FEE`,`INCLUDED_UNITS` (join PLAN_ID = ID) | `fn_entitlement` reads the plan fields with the covering subscription | `packages/02_pkg_plans.sql:53-68` |
| 13 (map-v3) | `date_format` + `raw_field: histDtRaw` | `subscriptionsHist` HIST_DT, format `%d-%b-%y %H:%M:%S`; `unparseable → null` | w1-b03 live recon FAIL under map-v2: 6/6 SUBSCRIPTIONS_HIST.HIST_DT rows are `DD-MON-YY HH24:MI:SS` text but map-v1/v2 carried only a `resolve` ("try both formats, keep raw") with no `date_format` op, so the family default DD-MON-YY applied; same policy as d-date-unparseable; the new op is ordered after that `resolve` (model_patch refuses a `resolve` whose question a preceding `date_format` already consumed) | `schema/01_tables.sql:218` — trigger writes TO_CHAR(SYSDATE,'DD-MON-YY HH24:MI:SS'); seeded rows measured YYYYMMDD 0% conformance → raw kept |

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

## (d) Units graded UNVERIFIED by the verifier, and why

Verifier evidence: branch `recon/wave-1-UNT9-7` — `.migration/recon/wave-1/wave-1-verify.json` (`run_id UNT9-7`, `manifest_sha ec9a01d04e88`), `verify-report.md`, 14 re-run `result.json` (mode live, target_class migration_cluster, map-v3 / tol-1 sha256 recomputed and matched). Batch-run evidence: the 14 `result.json` on the run branch under `.migration/recon/wave-1/<batch>/<unit>/` — all 14 PASS, 13 `merge_eligible true`, `customer-master` false.

| Unit (batch) | Collection | Verifier grade | Why | Batch-run evidence that stands |
|---|---|---|---|---|
| customer-master (w1-b01) | `customerMasterHist` | **UNVERIFIED** (`unverified_units`; harness PASS, `merge_eligible false`, warning verbatim `UNVERIFIED collection customerMasterHist: 0 source rows, key/shape/field rules unexercised`) | CUSTOMER_MASTER_HIST = 0 rows in `.migration/fixtures/mmprt-mini.json`; collection absent on the target (17 of 18 write targets exist); the history_copy key/shape/`date_format` rules (b.1-6) were never exercised by any data | `customerMaster` 201/201, T3 201 checks 0 findings, both runs; the unit's `merge_eligible false` was carried through UNT9-12, UNT9-10 r1 and UNT9-7 unchanged |
| billing-audit-log (w1-b02) | `billingAuditLog.loggedAt` | **UNVERIFIED on timestamp parity** — verifier re-run FAIL (T2 2 findings, T3 37/37), `verifier_batch_verdicts` DRIFT-EXPLAINED, `unit_verdicts` FAIL | `BILLING_AUDIT_LOG.LOGGED_AT` is the SYSDATE stamp `pkg_ow_util.log_msg` writes when `testdata/legacy/mmp_rt_exercise.sql` runs; the verifier re-seeded and re-exercised its own fixture (source 2026-10-08 13:32:23 vs target 12:11:03), source stable across three re-runs; keys, counts, module, message match. Fixture non-determinism, not a loader defect | batch-run `w1-b02/billing-audit-log/result.json`: PASS, merge_eligible true, warnings [], 0 findings (UNT9-11; re-gated under map-v3 in UNT9-10 r1) |
| subscriptions (w1-b03) | `subscriptionsHist.histDt` / `histDtRaw` | **UNVERIFIED on timestamp parity** — verifier re-run FAIL (T3 12 findings = 6 rows × 2 fields), DRIFT-EXPLAINED / FAIL as above | `SUBSCRIPTIONS_HIST.HIST_DT` = `TO_CHAR(SYSDATE,'DD-MON-YY HH24:MI:SS')` written by `TRG_SUBSCRIPTIONS_HIST` when the exercise closes the open subscriptions; same re-seed cause; the 20 `subscriptions` documents and the other 4 units of the batch PASS with 0 findings | batch-run `w1-b03/subscriptions/result.json`: PASS, merge_eligible true, 6/6 hist rows graded (UNT9-10 r1, map-v3) |

Wave form: `wave_verdict FAIL` (grader form: `preflight.py validate_verify` accepts only PASS/FAIL per batch, a PASS must be graded from a PASS `result.json`); `unit_verdicts` w1-b01 PASS, w1-b02 FAIL, w1-b03 FAIL, w1-b04 PASS, w1-b05 PASS; verifier's own batch verdicts PASS / DRIFT-EXPLAINED / DRIFT-EXPLAINED / PASS / PASS; 12 of 14 units PASS on independent live re-run. Plan gates `g-recon-pass-1` / `g-independent-verify-1` left unticked by the manager (UNT9-7 card). Probes past the gate found no defect: 17/17 collections match COUNT(*), 0 duplicate keys, `invoices.lines` 29/29 over 7 parents, 37/37 planted `invoiceLine.invoiceId` orphans preserved, 14 cross-unit reference checks 0 dangling both sides, `customerMaster.signupDt` null on 41/201 = the d-date-unparseable rule with raw kept (explained). Target footprint 2,460,371 B (data + index), 17 collections, 3,022 objects.

Not independently verified at all: Tier 4 / app parity (no `ops/` declared for this run, nothing to replay — every batch card and the verifier); every other unit is verified live by two independent runs on the same mapping bytes.

## (e) Plugin blind spots — every place a plugin tool was wrong or blind

Collected from the ticket cards UNT9-1…13, the merged PR bodies #1943–#1953 and `recon/wave-1-UNT9-7:verify-report.md` findings 1–13. Plugin pinned at `349cb2d17dccb246409e7750657e25843bf53be8`, unpatched; nothing below was worked around by editing the plugin.

| # | Step / tool | What was wrong or blind | Effect in this run | Source |
|---|---|---|---|---|
| e.1 | s1.1 — org-installed dbx guard (`hooks/dbx_guard.py`) | Rejects the plain Mongo `allowed_targets.json` (`databases` list); UNT8 finding P1 still present | Compat shape from #1916 re-applied: `catalogs`, `guard_mode: warn`, `_compat_note` (`.migration/allowed_targets.json`) | UNT9-1 card; PR #1943 |
| e.2 | s1.1 / s4.1 — environment blueprint | Blueprint note says the recon harness is preinstalled in `/home/ubuntu/.venvs/recon`; the venv had no `recon` entry point on two fresh hosts | Workers and verifier pip-installed `mongo-recon-harness 0.3.3` from the pinned clone before `recon selftest` | UNT9-1 card; verify-report finding 11 |
| e.3 | s1.2 — workload exporter | The `MMP_RT_SRC_DSN` principal cannot read `V$SQLAREA`/`V$SQLSTATS`; exporter had to run `--emit-sql` → read-only as fixture SYSTEM → `--from-results`; `workload.json` carries no provenance marker for that deviation | 115 statements, `schema_filtered true`, 4 `non_dml` rows skipped; the deviation lives only on the card | UNT9-2 card |
| e.4 | s1.2 — connectivity probe | `privilege_excess` on both sides (source: CREATE TABLE/PROCEDURE/TRIGGER/…; target: `readWriteAnyDatabase@admin`, `dbAdminAnyDatabase@admin`) → `blocked: true`, yet the run proceeds with `source_access live` / `target_access migration_cluster` | Recorded, nothing changed; the probe's block is advisory in practice | UNT9-2 card; `.migration/connectivity.json` |
| e.5 | s2.1 — access scan | `written_together` and `via_trigger` never appear (trigger patterns carry a `trigger{on,events}` block instead); `txn` on 1 of 10 hist/audit patterns; `via` on 1 pattern, `depth` on 14 | Unit derivation had to read the trigger DDL by hand to place the `_HIST` tables with their roots | UNT9-3 card; §a table |
| e.6 | s2.1 — data profile | `known_incompatibilities` key absent from `data_profile.json` | Recorded as a `note` decision; absence is a blind spot, not evidence of none | UNT9-3, UNT9-5 cards; §c |
| e.7 | s2.1 — access scan over `ops/` | `ops/` files are `.txt`, so the scan yields no patterns from them; 23 of 34 unfrequencied candidates were schema install/seed/upgrade scripts | Only 11 patterns confirmed by hand; no ops-sourced evidence | UNT9-4 card |
| e.8 | s3.1 — design `resolve` + `model_patch --check` | The pass resolved SUBSCRIPTIONS_HIST.HIST_DT with a `resolve` ("try both formats, keep raw") and emitted no `date_format`; `--check` did not flag a resolved date question with no rule | w1-b03 `subscriptions` FAIL under map-v2 (`date_unparseable`, 6/6 rows); fixed as b.13 → map-v3 | UNT9-10 card; PR #1951 |
| e.9 | s3.1 — `model_patch --check` | Surfaces `--census` / `--access-patterns` / `--data-profile` evidence one flag at a time | Three check invocations to reach exit 0 | UNT9-5 card; PR #1951 |
| e.10 | s3.1 — `model_patch` | Applies ops in decision order; a `date_format` for a question a preceding `resolve` already consumed is refused | b.13 had to be ordered after `resolve` #13 instead of in natural position | PR #1951 |
| e.11 | s3.1 / s4.0 — family default `unparseable: keep` | The default can never PASS recon on planted garbage dates (41 CUSTOMER_MASTER.SIGNUP_DT values) | w1-b01 `customer-master` FAIL under map-v1; plan decision d-date-unparseable → `raw_field`, map-v2 | UNT9-12 card; PR #1949 |
| e.12 | s3.3 — units / batching | 6 depth-0 units at ≤ 5 per batch forced 5 batch tickets (13 tickets vs the 12 target); batches may never span depths | One extra ticket (`w1-b02`, one unit) | UNT9-6 card; PR #1948 |
| e.13 | s3.3 — `preflight.py --emit-tickets` | Warns about artifacts it never reads (`05_decisions.md`, `units.json`, `workload.json`, …) | Noise on the preflight exit line | UNT9-6 card |
| e.14 | s4.0 — harness `recon run` | Without `--collections` the harness grades all 19 spec collections, not the unit's | Every worker passed `--collections <unit collections>` by hand | UNT9-12 card; PRs #1949–#1953 |
| e.15 | s4.0 — harness CLI vs ticket method | CLI requires `--canonicalization`; the ticket method omits it; `result.json` does not record the canonicalization file, so its identity is outside the graded evidence | Verifier passed `skills/mongo-migration/profiles/oracle.md` by hand | verify-report finding 6 |
| e.16 | s4.0 / s4.1 — `RECON_REDACT_SALT` | Unset on every host; all 28 `result.json` record `redaction_salted false` (unsalted hashes, low-entropy values enumerable offline) | Harness warning only | PRs #1949–#1953; verify-report finding 10 |
| e.17 | s4.0 — Tier 4 | Never run: no `--ops` recorded for any unit, no `ops/` directory in `.migration/` | App parity unverified for the whole wave | UNT9-11 card; every batch PR; verify-report probes |
| e.18 | s4.0 — mid-wave spec fix | A mapping correction after batches merged (map-v1→v2 in w1-b01, v2→v3 in w1-b03) forces re-grading every merged batch so `--grade` sees one `mapping_version` | 6 merged units re-gated gate-only in #1951; `manifest_sha` moved 0939e0b61b54 → 5715dd929db2 → ec9a01d04e88 | UNT9-10, UNT9-12 cards; PR #1951 |
| e.19 | s4.0 — `preflight.py --grade` | Reads `recon_results` from `origin/<PR branch>`, but PR branches are deleted at merge; wave-level `--grade` needs all five batch results at once | Manager graded per PR head before merge; the verifier could not reproduce `manifest_sha ec9a01d04e88` from the ticket block (8 canonical reconstructions) | UNT9-12 card; verify-report finding 12 |
| e.20 | s4.1 — `preflight.py --verify` | `verify_report_path` and `recon_results` hard-code `recon/wave-1` with no branch override; the ticket branch rule (`recon/wave-1-UNT9-7`, because `recon/wave-1` holds another run) is rejected (`report_path must be exactly recon/wave-1:…`) and three PASS batches are "not evidence" because the grader looks at another run's branch | `--verify` exit 1 with four problems; branch not renamed | UNT9-7 card; verify-report finding 5 |
| e.21 | s4.1 — `skills/wave-verify` vs `validate_verify` | The skill allows a per-batch DRIFT-EXPLAINED verdict; the validator accepts only PASS/FAIL | Drift carried in `verifier_batch_verdicts` beside FAIL `unit_verdicts`; `wave_verdict FAIL` for a wave with no defect found | verify-report finding 4 |
| e.22 | s1.2 / s4.1 — fixture manifest | `mmprt-mini.json` pins row counts but not the SYSDATE-stamped columns (`LOGGED_AT`, `HIST_DT`); the fixture is reproducible by count, not by value, so independent re-verification on a fresh host can never PASS w1-b02 or `subscriptions` | §d rows 2–3 | verify-report finding 3; UNT9-7 card |
| e.23 | s2.1 — pipeline step log | `spec_diff vs pinned` exits 1 on the one edge-rule change between draft-1 and draft-2 (`TENANTS→USAGE_EVENTS`) — a diff, not a failure, reported as a non-zero step | `.migration/pipeline_steps.txt` last line | UNT9-4 card |

## (f) ACU per ticket and total

Figures copied from the manager's hand-off on the UNT9-8 card (board attribution = the shared worker session split evenly across its tickets; observed = manager-measured per-ticket delta). Not estimated here.

| Ticket | Step | Board ACU | Observed |
|---|---|---|---|
| UNT9-1 | s1.1-scope | 4.89 | 4.85 |
| UNT9-2 | s1.2-fixture-probe | 5.54 | 8.6 |
| UNT9-3 | s2.1-pipeline | 5.54 | 3.0 |
| UNT9-4 | s2.2-access-review | 5.54 | 3.9 |
| UNT9-5 | s3.1-design-decisions | 5.54 | 6.9 |
| UNT9-6 | s3.3-units-preflight | 5.54 | 3.3 |
| UNT9-12 | w1-b01 | 5.54 | 6.2 |
| UNT9-11 | w1-b02 | 5.54 | 2.5 |
| UNT9-10 | w1-b03 | 5.54 | 6.1 |
| UNT9-9 | w1-b04 | 5.54 | 5.7 |
| UNT9-13 | w1-b05 | 5.54 | 5.4 |
| UNT9-7 | s4.1.verify | 9.71 | 9.7 |
| UNT9-8 | s5.1-record | 11.55 (board card at PR 2 open; the card keeps counting until the session ends) | — |

| Total | Value |
|---|---|
| Worker sessions | 70.0 (UNT9-1 4.89 + fixture-host session 55.43 for UNT9-2…13 + verifier 9.71) + UNT9-8 11.55 = 81.55 |
| Manager session | 51.4 at hand-off; no later figure had been posted on the UNT9-8 card when PR 2 opened — the manager's final number supersedes this row |
| Running total at hand-off | 121.4 of the 140 target |
| Running total at PR 2 open | 132.95 of the 140 target (81.55 worker + 51.4 manager at hand-off) |
| Tickets | 13 vs the 12 target (e.12) |
| Prior run (UNT8) | 24 tickets / ~425 ACU |
