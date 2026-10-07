# 04 — Migration units and the wave proposal

Plan step `s4.4-units` (phase: Model proposal, corrections and pinned mapping). Ticket UNT8-14. Depends on `s4.3-known-incompat` (UNT8-13, merged at `218dc441`).

| Run header | |
|---|---|
| Run branch | `tp-run/mongodb-20261007T161014Z` (base for this step: `218dc441`) |
| Plugin under test | `Cognition-Partner-Workshops/mongo-migration-plugin` @ `353280fc837193a40ccc005cb62fb4ffaf8ac16f` (clone `~/mmp`, unpatched, nothing pushed) |
| Mapping | `.migration/mapping_spec.json` **`map-v1.1`** sha256 `3dc4060d3a4bdc39f0904c3e79eff2568fb32e5560cad822280a0aa95b2539b6` (final pin, no further bumps) |
| Tolerances | `.migration/recon_tolerances.json` **`tol-1`** sha256 `a23d517a8e6d00c84f668c0016ef0e42b16625d45ab7e4166e3838abf241e3da` |
| Row counts | `.migration/fixtures/mmprt-mini.json` (`row_counts`, live `COUNT(*)` after the one-time package exercise) |
| Footprint basis | `.migration/data_profile.json` (`row_bytes:*`, `embed_bytes:*`, not sampled) |
| Target database | `mmp_rt_b4_oracle` (`.migration/allowed_targets.json`); secret by name only `MONGODB_ATLAS_URI` |
| Database access | none — this step is a static derivation from the pinned spec and the committed profile; no Oracle or Atlas query was run |
| Policy files | none edited (`allowed_targets.json`, `authorizations.json`, `recon_tolerances.json`, `mapping_spec.json` untouched) |
| Legacy estate | read-only, unchanged (`services/legacy-billing/db/oracle/`, `testdata/legacy/oracle_billing_seed.py`) |

## 1. Derivation rule

A **unit** is one aggregate-root collection of `map-v1.1` plus the collections it owns (its embedded children are
written in the same document, a `written_together` history table is written in the same Oracle transaction by a
trigger). Two roots share a unit only when the estate always writes them together (`SUBSCRIPTIONS` +
`SUBSCRIPTIONS_HIST` via `trg_subscriptions_hist`; `RATING_PERIODS` + `RATING_RESULTS` inside
`pkg_rating.sp_finalize_rating`; `INVOICE_HEADER` + `INVOICE_LINE` loaded by the one CUSTBILL batch). Shared /
reference lookups (`CODES`, `PLANS`, `TENANTS` — read by every package, written only by seed / admin paths and
`sp_suspend_overdue`) form their own unit so no two batches ever claim the same write target.

Dependency depth is the longest declared `FOREIGN KEY` chain from the unit's roots back to a depth-0 table
(`schema/01_tables.sql:70-165`). Logical pointers with no constraint (`CUSTOMER_MASTER.TENANT_ID`,
`CUSTOMER_MASTER_HIST.CUST_ID`, `INVOICE_LINE.INVOICE_ID` — `schema/02_horror.sql:408` "references ... usually")
do not add depth: the mapping carries them as plain fields and preserves unresolved values (`d-orphan-cm-tenant`,
`d-orphan-il-invoice`, `05_decisions.md`). An embedded child does not add depth either: it is written inside its
parent document.

Coverage arithmetic: 15 root collections + 4 embeds = **19 source tables**, all 19 of
`fixtures/mmprt-mini.json.row_counts` except `FIXTURE_META` (seed bookkeeping, not a migration unit — `05_decisions.md`).
Every table appears in exactly one unit below; every collection appears in exactly one write-target list.

## 2. Unit list

| unit_id | collections (write targets `mmp_rt_b4_oracle.<c>`) | source tables: roots / embedded / referenced | expected source rows | depth | batch |
|---|---|---|---|---|---|
| `u00-reference` | `codes`, `plans`, `tenants` (+ `tenants.creditNotes`) | roots `CODES`, `PLANS`, `TENANTS`; embedded `CREDIT_NOTES` → `tenants.creditNotes`; referenced — | CODES 32, PLANS 3, TENANTS 15, CREDIT_NOTES 5 | 0 | `w1-b0` |
| `u01-subscriptions` | `subscriptions`, `subscriptionsHist` | roots `SUBSCRIPTIONS`, `SUBSCRIPTIONS_HIST` (written together by `trg_subscriptions_hist`); referenced `TENANTS`, `PLANS` | SUBSCRIPTIONS 20, SUBSCRIPTIONS_HIST 6 | 1 | `w1-b2` |
| `u02-usage-events` | `usageEvents` | root `USAGE_EVENTS`; referenced `TENANTS` (+ `CODES` domain check in `trg_usage_events_check`) | USAGE_EVENTS 103 | 1 | `w1-b2` |
| `u03-rating` | `ratingPeriods`, `ratingResults` | roots `RATING_PERIODS`, `RATING_RESULTS` (written together by `sp_finalize_rating`); referenced `TENANTS`, `SUBSCRIPTIONS` | RATING_PERIODS 8, RATING_RESULTS 8 | 2 | `w1-b3` |
| `u04-invoices` | `invoices` (+ `invoices.lines`, `invoices.dunningAttempts`) | root `INVOICES`; embedded `INVOICE_LINES` → `invoices.lines`, `DUNNING_ATTEMPTS` → `invoices.dunningAttempts`; referenced `TENANTS`, `RATING_PERIODS` | INVOICES 9, INVOICE_LINES 29, DUNNING_ATTEMPTS 5 | 2 | `w1-b3` |
| `u05-notifications` | `notifications` | root `NOTIFICATIONS`; referenced `TENANTS` | NOTIFICATIONS 2 | 1 | `w1-b2` |
| `u06-audit-log` | `billingAuditLog` | root `BILLING_AUDIT_LOG` (detached: autonomous transaction, never embedded — `d-audit-detached`); referenced — | BILLING_AUDIT_LOG 73 | 0 | `w1-b1` |
| `u07-customer-master` | `customerMaster` (+ `customerMaster.attributes`) | root `CUSTOMER_MASTER`; embedded `ENTITY_ATTR_VALUE` (`ENTITY_TYPE = 'CUSTOMER'`, the only observed domain) → `customerMaster.attributes`; referenced — (`TENANT_ID` is an unconstrained pointer, 200/201 unresolved by design) | CUSTOMER_MASTER 201, ENTITY_ATTR_VALUE 70 | 0 | `w1-b1` |
| `u08-customer-master-hist` | `customerMasterHist` | root `CUSTOMER_MASTER_HIST` (`trg_customer_master_hist` `:OLD` copies); referenced — (`CUST_ID` unconstrained pointer to `CUSTOMER_MASTER`) | **CUSTOMER_MASTER_HIST 0 → UNVERIFIED by design** | 0 | `w1-b1` |
| `u09-custbill-invoices` | `invoiceHeader`, `invoiceLine` | roots `INVOICE_HEADER`, `INVOICE_LINE` (CUSTBILL estate, loaded by one batch; **not** embedded — 37 ghost lines retained, `d-orphan-il-invoice`); referenced — | INVOICE_HEADER 1000, INVOICE_LINE 1500 | 0 | `w1-b1` |

Totals: 10 units, 15 collections, 4 embeds, 19 tables, **2 980 root documents** (plus 109 embedded sub-documents:
5 credit notes, 29 invoice lines, 5 dunning attempts, 70 EAV attributes).

### 2.1 Why these boundaries (evidence)

* `u00-reference` — `CODES` is read by every package through `pkg_ow_util.f_code_desc` (ap-d9d4207c37) and by
  `trg_usage_events_check` (ap-fe087c4e0c); `PLANS` by `fn_list_plans` / `fn_entitlement` / `compute_rating` /
  `compute_preview`; `TENANTS` by `fn_entitlement`, `compute_preview`, `fn_overdue_accounts`, `sp_suspend_overdue`.
  They are written only by seed / upgrade scripts (cold) and — `TENANTS.status_cd` — by `sp_suspend_overdue`
  (ap-8e4baaa9a0). `CREDIT_NOTES` is read and written only with its tenant (`compute_preview` ap-2e59f9675d,
  `sp_issue_invoice` ap-b259650bfe / ap-7a575dfc2d) → embedded `tenants.creditNotes` (`map-v1.1`), so it rides with
  the reference unit rather than with invoices.
* `u01-subscriptions` — `SUBSCRIPTIONS_HIST` has no reader anywhere in the estate; its only writer is
  `trg_subscriptions_hist` (`schema/01_tables.sql:206-222`, ap-bdfdef0db0) inside the `sp_change_plan` /
  `sp_suspend_overdue` UPDATE transaction (`written_together`, `03_access_review.md`). Separate collection
  (`design_decisions.json` `reference` op `subscriptions` ← `SUBSCRIPTIONS_HIST`, document_versioning in its
  revisions-collection form), same unit.
* `u03-rating` — `sp_finalize_rating` upserts `RATING_PERIODS` then `RATING_RESULTS` in one call
  (`packages/03_pkg_rating.sql:185-214`, ap-8e58932397 / ap-8ee13949bc / ap-d7af986eeb / ap-76af3595e0); the only
  reader of `RATING_RESULTS` joins it to `RATING_PERIODS` (`compute_rating` ap-81929b0d21).
* `u04-invoices` — `INVOICE_LINES` is read only by parent key (`fn_invoice_lines` ap-620d0a2057) and written only
  inside `sp_issue_invoice` (ap-5c6c87e418 / ap-56d46b7c81; `ON DELETE CASCADE`); `DUNNING_ATTEMPTS` is read only by
  parent key (`sp_schedule_dunning` ap-37287a11b5) → both embedded (`map-v1.1`).
* `u06-audit-log` — `pkg_ow_util.log_msg` is `PRAGMA AUTONOMOUS_TRANSACTION` (`packages/01_pkg_util.sql:66-77`,
  ap-779ce5b5b7): a row survives the caller's rollback, so it can never be embedded in the caller's aggregate
  (`d-audit-detached`); `JOB_PURGE_AUDIT_LOG` is its only deleter (ap-e7b18e81b8, disabled in the fixture).
* `u07-customer-master` — the facade reads `ENTITY_ATTR_VALUE` with the customer (`facade.py` ap-6c1786cb2d) and the
  profile shows at most one attribute per entity (`eav_shape`), so the EAV rows embed as `attributes`
  (`d-eav-embed`); CUSTBILL loads `CUSTOMER_MASTER` as its own system of record (`02_dependency_register.md` §2).
* `u08-customer-master-hist` — same `written_together` shape as `SUBSCRIPTIONS_HIST` (`trg_customer_master_hist`,
  `schema/02_horror.sql:358-374`, ap-dbf1b410e9) but kept as **its own unit**: the trigger never fired in the
  fixture (0 rows), so grouping it with `u07` would put a warning on an otherwise gradable unit. It is the only unit
  whose every root has 0 source rows; the harness grades it **UNVERIFIED** (`report.py`: "0 source rows,
  key/shape/field rules unexercised"). Recorded, not seeded around.
* `u09-custbill-invoices` — `INVOICE_HEADER` / `INVOICE_LINE` are read only by the CUSTBILL reports and extractor
  (`reports.py` ap-6167f9171f / ap-89c88ad4c6, `oracle_custbill_extract.py` ap-fa4086177d) in batch scope, never
  per parent; 37 of 1 500 lines point at no header (`data_profile.json`
  `pointer_resolve:INVOICE_LINE.INVOICE_ID->INVOICE_HEADER`), so lines stay a separate collection and the orphans
  are loaded verbatim (`d-orphan-il-invoice`).

## 3. Access evidence and representative read operations per unit

Every unit has a `.migration/ops/<unit_id>.json` in the harness `--ops` format
(`~/mmp/skills/mongo-recon-harness/SKILL.md`): a JSON list of `{name, source_sql, collection, target_pipeline,
rules}` (plus a free-text `evidence` field the harness ignores). All 27 `source_sql` strings are single read-only
`SELECT`s lifted from the package / application bodies cited, with the bind variables widened to the whole domain so
the row sets are comparable; they were checked with the plugin's own validators (`recon.cli._load_ops`,
`_validate_sql`, `recon.adapters._validate_pipeline`, every `collection` resolves in `map-v1.1`, every rule name in
the `rules` list resolves in the merged `profiles/oracle.md` + `map-v1.1-canon` rule set). Tier 4 itself runs only
in the batch tickets, with a source and a target executor; nothing here is a recon verdict.

| unit_id | package procedures / functions that are its access evidence | ops file (operation names) |
|---|---|---|
| `u00-reference` | `pkg_ow_util.f_code_desc` (ap-d9d4207c37); `pkg_plans.fn_list_plans` (ap-33e1dc2584), `fn_entitlement` (ap-df26fbfed9 / ap-60ec05ff91 / ap-95a0f9e481); `pkg_rating.compute_rating` plan read (ap-cd877ffc6d); `pkg_invoicing.compute_preview` tenant + credit-note reads (ap-41de3e5203, ap-2e59f9675d); `sp_issue_invoice` credit-note read/write (ap-b259650bfe, ap-7a575dfc2d); `pkg_dunning.sp_suspend_overdue` tenant read/write (ap-c089416cd9, ap-8e4baaa9a0); `trg_usage_events_check` (ap-fe087c4e0c) | `ops/u00-reference.json`: `codes-lookup-domain`, `plans-fn-list-plans`, `tenants-open-credit-notes` |
| `u01-subscriptions` | `pkg_plans.sp_change_plan` (ap-781940a6e5 read, ap-a7af1a6156 write); `pkg_rating.compute_rating` / `sp_finalize_rating` covering-subscription reads (ap-22fec4f2aa, ap-1fe02141ee, ap-b6d8685d76, ap-2cc202a47e); `pkg_invoicing.compute_preview` (ap-ee373ebbd1, ap-160686ae25); `pkg_dunning.sp_suspend_overdue` write (ap-d3754b6b8a); `trg_subscriptions_hist` (ap-bdfdef0db0) | `ops/u01-subscriptions.json`: `subscriptions-open-for-change-plan`, `subscriptions-covering-feb-2026`, `subscriptions-hist-revisions` |
| `u02-usage-events` | `pkg_rating.compute_rating` usage loop (ap-61c2839e36); `pkg_rating.fn_usage_summary` (ap-2b3995792f); facade usage read / write (ap-3fbad6ec1e, ap-d0babb7b83); `trg_usage_events_check` (ap-fe087c4e0c) | `ops/u02-usage-events.json`: `usage-fn-usage-summary-feb-2026`, `usage-compute-rating-used-units`, `usage-kind-domain-trigger-check` |
| `u03-rating` | `pkg_rating.compute_rating` rollover read (ap-81929b0d21); `pkg_rating.sp_finalize_rating` period upsert (ap-8e58932397, ap-8ee13949bc) and result upsert (ap-d7af986eeb, ap-76af3595e0); facade invoice/period read (ap-15404b0226) | `ops/u03-rating.json`: `rating-rollover-by-tenant`, `rating-periods-by-tenant`, `rating-results-billable` |
| `u04-invoices` | `pkg_invoicing.fn_invoice_lines` (ap-620d0a2057); `pkg_invoicing.sp_issue_invoice` (ap-c026ebf3a8, ap-c43f1f14dc, ap-75910aef55, ap-5c6c87e418, ap-56d46b7c81); `pkg_dunning.fn_overdue_accounts` (ap-46a8eb988b); `pkg_dunning.sp_schedule_dunning` (ap-644c102b12, ap-37287a11b5, ap-68fdfcc880); `pkg_dunning.sp_suspend_overdue` invoice read (ap-eb72a29af5); facade reads (ap-0da411e03b, ap-0a1051eac3) | `ops/u04-invoices.json`: `invoices-fn-overdue-accounts`, `invoices-fn-invoice-lines`, `invoices-next-dunning-attempt` |
| `u05-notifications` | `pkg_dunning.sp_suspend_overdue` dedupe read + insert (ap-d0e6a55401, ap-7692fe1e9a) | `ops/u05-notifications.json`: `notifications-suspension-dedupe`, `notifications-by-tenant-kind` |
| `u06-audit-log` | `pkg_ow_util.log_msg` (ap-779ce5b5b7) called from every package entry point; `JOB_PURGE_AUDIT_LOG` (ap-e7b18e81b8); `trg_billing_audit_log_id` (`schema/01_tables.sql:179-187`) | `ops/u06-audit-log.json`: `audit-entries-by-module`, `audit-issued-invoice-entries` |
| `u07-customer-master` | `reports.py` `BALANCES_SQL` (ap-c9b3d38c2c); facade `GET /customer` reads (ap-bd510b9356, ap-e45fe9768e) and EAV read (ap-6c1786cb2d); `oracle_custbill_extract.py` (ap-fa4086177d) | `ops/u07-customer-master.json`: `customer-balances-by-conversion-batch`, `customer-first-by-tenant`, `customer-eav-attributes` |
| `u08-customer-master-hist` | `trg_customer_master_hist` (ap-dbf1b410e9) — write-only path, **no reader in the estate**; 0 rows in the fixture | `ops/u08-customer-master-hist.json`: `customer-hist-revisions`, `customer-hist-raw-timestamps` (both compare 0 = 0; UNVERIFIED by design) |
| `u09-custbill-invoices` | `reports.py` `STATUS_SQL` (ap-6167f9171f), `LINE_SQL` (ap-89c88ad4c6); `oracle_custbill_extract.py` (ap-fa4086177d); operations handbook "ghost lines" (`02_dependency_register.md` §2) | `ops/u09-custbill-invoices.json`: `custbill-header-status-by-batch`, `custbill-lines-by-batch-type`, `custbill-ghost-lines` |

Operation conventions, so the batch worker does not have to rediscover them:

* Package reads that take one key (`fn_invoice_lines(:invoice_id)`, `f_code_desc(:type, :val)`, the `NVL(MAX(attempt_no), 0)`
  sub-select) are replayed over the whole domain — same projection, no bind — so one op covers every parent.
* Cursor loops that aggregate in PL/SQL (`compute_rating` usage loop, `compute_preview` credit-note loop) are folded
  to the equivalent `GROUP BY` / `$group`; the Mongo side reads the embed (`$filter`/`$size`/`$unwind`) where the
  Oracle side joins the child table.
* Joins that would cross a unit boundary are dropped and the op is scoped to the unit's own collections
  (`fn_overdue_accounts` without `TENANTS`, `STATUS_SQL` without the `CODES` label join), because Tier 4 greps one
  unit at a time and a cross-unit `$lookup` would make a PASS depend on another batch's load order. The only
  `$lookup`s are intra-unit (`ratingResults → ratingPeriods`, `invoiceLine → invoiceHeader`).
* `DECODE(tier_cd …)` / `DECODE(kind_cd …)` labels are reproduced with `$switch` so the compared value is the label the
  package returns, not the raw code. The exercised rating period (`2026-02-01 .. 2026-02-28`,
  `testdata/legacy/mmp_rt_exercise.sql`) is used where a package takes a period.
* `rules` on every op = `decimal_round`, `datetime_utc_truncate_ms`, `empty_string_is_null`, `null_missing_equiv`
  (the `tol-1` / `map-v1.1-canon` set that applies to every projected type). No op uses `csv_to_array`, `yn_to_bool`
  or the `date_string_to_date:*` aliases because none projects a raw-text date or CSV column: those fields are graded
  by Tier 2/3 field rules, where the mapping carries both the raw and the parsed value (`d-hist-dt`, `d-dirty-dates`).
* Sort order is part of only two ops (`plans-fn-list-plans`, `invoices-fn-invoice-lines`), both with a total order.

## 4. Estimated Atlas footprint per unit

Basis: `row_bytes:<table>.avg_bytes × row_counts` from `data_profile.json` (Oracle `VSIZE` bytes of the loaded
rows, not sampled). BSON documents with camelCase field names and type bytes are estimated at **2× raw** (the
mini fixture's columns are short codes, ids and numbers, so field names roughly double the payload); indexes at
**64 B per document per index**, index count = `map-v1.1` `indexes[]` + `_id`. These are estimates for the
10 MB budget, not measured Atlas `storageSize`; the batch tickets record the measured `collStats` after load.

| unit_id | root docs | raw source KiB | BSON est. KiB | index est. KiB | **est. total KiB** |
|---|---|---|---|---|---|
| `u00-reference` | 50 | 1.9 | 3.9 | 10.5 | **14.4** |
| `u01-subscriptions` | 26 | 3.2 | 6.3 | 5.8 | **12.1** |
| `u02-usage-events` | 103 | 8.4 | 16.9 | 12.9 | **29.7** |
| `u03-rating` | 16 | 1.7 | 3.3 | 2.0 | **5.3** |
| `u04-invoices` | 9 | 4.3 | 8.6 | 3.9 | **12.5** |
| `u05-notifications` | 2 | 0.2 | 0.3 | 0.2 | **0.6** |
| `u06-audit-log` | 73 | 6.2 | 12.4 | 9.1 | **21.5** |
| `u07-customer-master` | 201 | 70.8 | 141.5 | 37.7 | **179.2** |
| `u08-customer-master-hist` | 0 | 0.0 | 0.0 | 0.0 | **0.0** (empty collection + 2 index definitions) |
| `u09-custbill-invoices` | 2 500 | 541.6 | 1 083.1 | 156.2 | **1 239.4** |
| **total** | **2 980** | **638.1** | **1 276.3** | **238.3** | **≈ 1 515 KiB ≈ 1.5 MiB** |

Even at 4× raw instead of 2× the total stays under 3 MiB; the 10 MB budget on `mmp_rt_b4_oracle` holds with
margin, and `u09-custbill-invoices` (82 % of the total) is the only unit whose size is worth re-measuring after load.
Embedded children are included in their parent's raw bytes (`CREDIT_NOTES` 0.4 KiB in `u00`, `INVOICE_LINES` +
`DUNNING_ATTEMPTS` 3.2 KiB in `u04`, `ENTITY_ATTR_VALUE` 5.2 KiB in `u07`); the largest single document the profile
predicts is a `tenants` document with its credit notes (`embed_bytes:CREDIT_NOTES->TENANTS` p99 166 B + 53 B root),
far below the 16 MB document limit.

## 5. Wave proposal (decision `d-wave-shape`: one wave)

One wave, four batches, 1–5 units each, every batch at one dependency depth, write targets disjoint, the reference
unit first in its own batch. `auto_merge: false` — `.migration/connectivity.json` records both access axes as
**blocked** (over-scoped principals, `source_access: live`, `target_access: migration_cluster`), so until that is
lifted no batch can produce merge evidence (`merge_eligible` needs live/snapshot source + migration-cluster target +
PASS + no warnings); fixture / local-target runs are evidence of the mapping, not of the merge.

| batch id | depth | units | write targets (`mmp_rt_b4_oracle.*`) | root docs | note |
|---|---|---|---|---|---|
| `w1-b0-reference` | 0 | `u00-reference` | `codes`, `plans`, `tenants` | 50 | reference unit alone, first; every later batch's `$lookup`-free ops still assume these exist for FK sanity |
| `w1-b1-detached-depth0` | 0 | `u06-audit-log`, `u07-customer-master`, `u08-customer-master-hist`, `u09-custbill-invoices` | `billingAuditLog`, `customerMaster`, `customerMasterHist`, `invoiceHeader`, `invoiceLine` | 2 774 | no declared FK to anything; `u08` grades UNVERIFIED by design (expected, not a FAIL) |
| `w1-b2-tenant-children-depth1` | 1 | `u01-subscriptions`, `u02-usage-events`, `u05-notifications` | `subscriptions`, `subscriptionsHist`, `usageEvents`, `notifications` | 131 | FK → `TENANTS` / `PLANS` (batch `w1-b0`) |
| `w1-b3-rating-invoicing-depth2` | 2 | `u03-rating`, `u04-invoices` | `ratingPeriods`, `ratingResults`, `invoices` | 25 | FK → `SUBSCRIPTIONS` (`w1-b2`), `TENANTS` (`w1-b0`); `invoices` also → `ratingPeriods` inside the same unit set |

Order of batches is the depth order above; `w1-b0` and `w1-b1` are both depth 0 and could run concurrently, but the
reference batch is listed first per the plan. Every batch carries `mapping_version map-v1.1` /
`mapping_sha256 3dc4060d…539b6`, `recon_tolerances_version tol-1` / `tolerance_sha256 a23d517a…3da`, and
`fixture_manifest .migration/fixtures/mmprt-mini.json`.

### 5.1 Preflight

The proposal above was written as a wave spec and run through the plugin's `wave-preflight` (unpatched) from the
repo root:

```
python3 ~/mmp/skills/wave-preflight/preflight.py --wave <spec> --root . --emit-tickets
→ exit 0, manifest_sha a00f32f7a171, 4 ticket blocks, no write-target collision
```

The committed wave manifest (`.migration/waves/…`) is the wave-plan step's deliverable, not this one; the spec that
produced `a00f32f7a171` is exactly the table in §5 with the hashes above, `wave: 1`, `auto_merge: false`,
`source_access: live`, `target_access: migration_cluster`.

**Finding fixed in this PR — fixture manifest shape.** The first preflight run refused every batch with
`fixture manifest .migration/fixtures/mmprt-mini.json is missing 'produced_by'`: `preflight.py` requires
`produced_by` to be a non-empty **string**, and the manifest committed by the fixture step carried an object
(wrapper / seeder blob SHAs, exercise script, run-branch head, plugin head). This PR folds that object into a
one-line `produced_by` string and keeps the structured provenance verbatim under a new `producers` key; no other
manifest field changed (`row_counts`, `masked_columns`, `method: synthetic`, `produced_at` untouched), so no
count or hash cited by earlier steps moves. Without this change the wave planner cannot ticket any batch.

Preflight also prints the layout warning that `.migration/ops` and the `.migration/*.md` step reports "are not read
by any tool". The `ops/` directory is where the plan step told this ticket to put the `--ops` files and the `*.md`
reports are the board's evidence convention since `01_census_crosscheck.md`; the warning is informational (exit 0)
and left as is — nothing in `.migration/` was moved or renamed.

## 6. Pre-PR self-check (`.agents/skills/tp-pre-pr-self-check/SKILL.md`)

| item | status |
|---|---|
| NULL / missing attribution cannot fail open | n/a to this step (no load, no recon run); the ops use `NVL(SUM(..), 0)` ↔ `$ifNull` symmetrically and `null_missing_equiv` so a missing field and a NULL compare equal, never silently pass as a value |
| Every namespace reference scoped | every write target is `mmp_rt_b4_oracle.<collection>` (the allowlisted database); no other database, catalog or schema is named as a target |
| No DDL drops / replaces / alters a shared table | none — no DDL, no SQL executed; legacy estate untouched (`git diff --stat` shows only `.migration/`) |
| Retention / cleanup safe on rerun | n/a — no cleanup logic; the ops files are read-only `SELECT`s and the wave spec is re-derivable |
| Cleanup retains evidence | n/a; this step adds evidence (`04_units.md`, `ops/*.json`), removes nothing |
| No secrets | none: the only credential reference is the secret **name** `MONGODB_ATLAS_URI`; `git grep` for `mongodb+srv`, `@`-urls and `password` over the diff returns nothing |
| Parity vs tolerance matches the contract | the ops carry only rules from the pinned `tol-1` / `map-v1.1-canon` set; no new rule or tolerance was invented |
| Idempotency proven by rerun | `preflight.py` and the ops validators were run twice with identical output (`manifest_sha a00f32f7a171` both times); no data path exists yet to rerun |
| Recon values recomputed, not copied | no recon values are stated; counts come from `fixtures/mmprt-mini.json`, sizes from `data_profile.json` (both committed, cited) |
| Unverified / untested paths listed | `u08-customer-master-hist` UNVERIFIED by design (§2.1); Tier 4 ops not yet executed against Oracle or Atlas (both access axes blocked, `connectivity.json`); footprint is an estimate, not `collStats` |
| Recon report `kind: recon-report` | n/a — no recon report is produced by this step |
| Capability preflight passed | `wave-preflight` exit 0 (§5.1); `.migration/connectivity.json` still reports source and target **blocked** — that blocker is carried forward, not hidden |
| `make tp-smoke` green | yes — `tp-smoke: all checks passed` on this branch (the first attempt stopped at `mise trust` for the repo's `mise.toml`, an environment step, not a repo failure; rerun green) |
