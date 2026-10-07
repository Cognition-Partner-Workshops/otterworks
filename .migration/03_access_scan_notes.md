# 03 — Access scan notes (s3.1-access-scan, UNT8-9)

Raw scanner evidence for the reviewer (`s3.2-access-review`). Nothing in
`.migration/access_patterns.json` is confirmed: every candidate has
`confirmed: false`, `frequency: null`, no `pinned`. `deploy_script: true` is
left exactly as the default globs set it. The estate was not edited.

- Run branch: `tp-run/mongodb-20261007T161014Z`
- Plugin: `Cognition-Partner-Workshops/mongo-migration-plugin` @ `353280fc837193a40ccc005cb62fb4ffaf8ac16f` (clone `~/mmp`, unpatched)
- Skill: `skills/schema-modeling/SKILL.md` §4 (`access_scan.py` + `access_scan_sql.py`)
- Census input: `.migration/census.json` (sha256 `af73f0b7da5aee92392f36f87e20b75f21080077f0e56f8c436d1d530bcd1219`, 20 tables, 7 triggers, 2 scheduler jobs)
- Command (run from the run-branch root):

```
python3 ~/mmp/skills/schema-modeling/access_scan.py \
  --census .migration/census.json \
  --root services/legacy-billing/db/oracle/packages \
  --root services/legacy-billing/db/oracle/schema \
  --root services/legacy-billing/db/oracle/ops \
  --out .migration/access_patterns.json
```

`services/legacy-billing/db/procs/` (Postgres port) was NOT added as a root.
`access_scan.validate_access(doc, census)` on the output returns no errors.

## 1. What the scanner covered

Scanner file filter (`_FILE_EXTS` in `access_scan.py`): `.java .kt .scala .py
.rb .cs .ts .js .go .php .xml .sql .sh .bash .ksh`. `.txt` is not in the set.

| Root | Files present | Read | Skipped (not scannable) | Candidates |
|---|---|---|---|---|
| `packages/` | `01_pkg_util.sql`, `02_pkg_plans.sql`, `03_pkg_rating.sql`, `04_pkg_invoicing.sql`, `05_pkg_dunning.sql` | 5 | 0 | 2 + 7 + 12 + 12 + 11 = 44 |
| `schema/` | `01_tables.sql`, `02_horror.sql`, `03_seed_static.sql`, `04_jobs.sql`, `04_upgrade_static.sql` | 5 | 0 | 3 + 2 + 14 + 1 + 22 = 42 |
| `ops/` | `deploy_prod_FINAL_v2.sh.txt`, `OPERATIONS_HANDBOOK.doc.txt` | 0 | 2 | 0 (scanner stdout: `root services/legacy-billing/db/oracle/ops: 0 scannable files`) |

So `ops/*.sh.txt` and `ops/*.doc.txt` were **not parsed at all**; the `ops`
root contributed nothing. Not in any requested root (by ticket design, listed
so the reviewer knows they are unscanned): `oracle/setup/01_users.sql`,
`oracle/startup/00_init.sh` (contains `MERGE INTO fixture_meta`, lines 52-59
and 155-162, and drives the whole schema/package load), `oracle/README.md`,
`testdata/legacy/oracle_billing_seed.py` (the bulk seeder for the `02_horror`
tables).

Totals: **86 candidates** — 42 `read`, 44 `write`; 38 `deploy_script: true`
(all of `03_seed_static.sql` and `04_upgrade_static.sql` via the `*seed*` /
`*upgrade*` globs, plus the two literal `INSERT INTO codes` in `01_tables.sql:17`
and `02_horror.sql:9`, which the scanner flags because the file also contains
`CREATE TABLE` and the DML has no routine). 0 `confirmed`, 0 non-null
`frequency`, 0 `pinned`.

Keys that appear in the output: `cascades current_of deploy_script drives_loop
in_loop invoked_by may_rollback nested_in outer_edges schedule_hint trigger`.
Keys that **never** appear: `txn`, `identity_capture` (see §6).

## 2. Candidate count per routine

| Routine | Candidates | Ids |
|---|---|---|
| `pkg_ow_util` (total) | 2 | |
| `pkg_ow_util.f_code_desc` | 1 | `ap-d9d4207c37` (read CODES, dynamic SQL via `EXECUTE IMMEDIATE`, `01_pkg_util.sql:40`) |
| `pkg_ow_util.log_msg` | 1 | `ap-779ce5b5b7` (write BILLING_AUDIT_LOG, `01_pkg_util.sql:70-71`) |
| `pkg_ow_util.f_md5_uuid`, `f_dt2str`, `f_str2dt` | 0 | `dual`-only / no SQL |
| `pkg_plans` (total) | 7 | |
| `pkg_plans.fn_list_plans` | 1 | `ap-33e1dc2584` |
| `pkg_plans.fn_entitlement` | 3 | `ap-df26fbfed9`, `ap-60ec05ff91`, `ap-95a0f9e481` (nested in `ap-60ec05ff91`) |
| `pkg_plans.sp_change_plan` | 3 | `ap-781940a6e5`, `ap-a7af1a6156`, `ap-875f85e898` |
| `pkg_rating` (total) | 12 | |
| `pkg_rating.compute_rating` | 5 | `ap-22fec4f2aa`, `ap-1fe02141ee` (nested), `ap-cd877ffc6d`, `ap-61c2839e36`, `ap-81929b0d21` |
| `pkg_rating.fn_usage_summary` | 1 | `ap-2b3995792f` |
| `pkg_rating.sp_finalize_rating` | 6 | `ap-b6d8685d76`, `ap-2cc202a47e` (nested), `ap-8e58932397`, `ap-8ee13949bc`, `ap-d7af986eeb`, `ap-76af3595e0` |
| `pkg_rating.fn_usage_rating` | 0 | `dual`-only cursor; calls `compute_rating` (`03_pkg_rating.sql:126`) |
| `pkg_invoicing` (total) | 12 | |
| `pkg_invoicing.compute_preview` | 4 | `ap-ee373ebbd1`, `ap-160686ae25` (nested), `ap-2e59f9675d`, `ap-41de3e5203` |
| `pkg_invoicing.fn_invoice_lines` | 1 | `ap-620d0a2057` |
| `pkg_invoicing.sp_issue_invoice` | 7 | `ap-c026ebf3a8`, `ap-c43f1f14dc`, `ap-5c6c87e418`, `ap-56d46b7c81`, `ap-75910aef55`, `ap-b259650bfe`, `ap-7a575dfc2d` |
| `pkg_invoicing.fn_invoice_preview` | 0 | `dual`-only; calls `compute_preview` |
| `pkg_dunning` (total) | 11 | |
| `pkg_dunning.fn_overdue_accounts` | 1 | `ap-46a8eb988b` |
| `pkg_dunning.sp_schedule_dunning` | 3 | `ap-644c102b12`, `ap-37287a11b5`, `ap-68fdfcc880` |
| `pkg_dunning.sp_suspend_overdue` | 7 | `ap-eb72a29af5`, `ap-c089416cd9`, `ap-8e4baaa9a0`, `ap-d3754b6b8a`, `ap-7692fe1e9a`, `ap-cd2440f5ed` (nested), `ap-d0e6a55401` (nested) |
| `trg_billing_audit_log_id` | 0 | see §7 |
| `trg_subscriptions_hist` | 1 | `ap-bdfdef0db0` |
| `trg_sub_no_uncancel` | 0 | see §7 |
| `trg_usage_events_check` | 1 | `ap-fe087c4e0c` |
| `trg_customer_master_seq` | 0 | see §7 |
| `trg_customer_master_hist` | 1 | `ap-dbf1b410e9` |
| `trg_entity_attr_value_seq` | 0 | see §7 |
| `job:JOB_NIGHTLY_DUNNING` | 0 own rows | job body is only procedure calls; surfaces as `invoked_by: [{04_jobs.sql, line 13}]` + `schedule_hint: "daily"` on all 10 `sp_schedule_dunning` / `sp_suspend_overdue` rows |
| `job:JOB_PURGE_AUDIT_LOG` | 1 | `ap-e7b18e81b8` (write/DELETE BILLING_AUDIT_LOG, `04_jobs.sql:24`, `schedule_hint: "daily"`) |
| (no routine — deploy DML) | 38 | `01_tables.sql` 1, `02_horror.sql` 1, `03_seed_static.sql` 14, `04_upgrade_static.sql` 22 |

`schedule_hint` is `"daily"` for both jobs; the `BYHOUR=2` / `BYHOUR=3;BYMINUTE=30`
parts of the `repeat_interval` are not carried into the output.

## 3. Every `trigger` row

| Id | op | table written/read | routine | `trigger` | `detached` | `may_rollback` | source |
|---|---|---|---|---|---|---|---|
| `ap-bdfdef0db0` | write | SUBSCRIPTIONS_HIST | `trg_subscriptions_hist` | `{"on":"SUBSCRIPTIONS","events":["update","delete"]}` | — | — | `schema/01_tables.sql:213-222` |
| `ap-fe087c4e0c` | read | CODES | `trg_usage_events_check` | `{"on":"USAGE_EVENTS","events":["insert"]}` | — (see note) | `true` (`RAISE_APPLICATION_ERROR`, line 251) | `schema/01_tables.sql:248-249` |
| `ap-dbf1b410e9` | write | CUSTOMER_MASTER_HIST | `trg_customer_master_hist` | `{"on":"CUSTOMER_MASTER","events":["update","delete"]}` | — | — | `schema/02_horror.sql:365-372` |

No row carries `detached`. The scanner only sets `detached: "autonomous"` when
`PRAGMA AUTONOMOUS_TRANSACTION` appears inside a trigger body; none of the
seven triggers has one, so the absence is consistent with the source
(`grep PRAGMA schema/*.sql` → nothing). The only autonomous unit in the estate
is `pkg_ow_util.log_msg` (§6).

## 4. Every write whose `cascades` names a trigger pattern

| Write id | op / table | routine | source | `cascades` → | trigger events | scanner basis |
|---|---|---|---|---|---|---|
| `ap-a7af1a6156` | UPDATE SUBSCRIPTIONS (`CURRENT OF c_open_subs`) | `pkg_plans.sp_change_plan` | `02_pkg_plans.sql:91-94` | `ap-bdfdef0db0` (`trg_subscriptions_hist`) | update/delete | UPDATE → fires |
| `ap-875f85e898` | INSERT SUBSCRIPTIONS (dynamic SQL) | `pkg_plans.sp_change_plan` | `02_pkg_plans.sql:101` | `ap-bdfdef0db0` | update/delete | INSERT matched as {insert,update} — **over-approximation**, AFTER UPDATE OR DELETE does not fire on INSERT |
| `ap-d3754b6b8a` | UPDATE SUBSCRIPTIONS | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:82-84` | `ap-bdfdef0db0` | update/delete | UPDATE → fires |
| `ap-453b668254` | INSERT SUBSCRIPTIONS (seed) | — | `03_seed_static.sql:24` | `ap-bdfdef0db0` | update/delete | same over-approximation |
| `ap-0f6d62e335` | INSERT SUBSCRIPTIONS (seed) | — | `03_seed_static.sql:25` | `ap-bdfdef0db0` | update/delete | same over-approximation |
| `ap-1bee089176` | INSERT…SELECT…NOT EXISTS SUBSCRIPTIONS (upgrade) | — | `04_upgrade_static.sql:28-38` | `ap-bdfdef0db0` | update/delete | same over-approximation |
| `ap-27ea66fd68` | INSERT USAGE_EVENTS (seed) | — | `03_seed_static.sql:35` | `ap-fe087c4e0c` (`trg_usage_events_check`) | insert | BEFORE INSERT → fires |
| `ap-5fa2aaf612` | INSERT…SELECT USAGE_EVENTS (upgrade) | — | `04_upgrade_static.sql:40-48` | `ap-fe087c4e0c` | insert | fires |
| `ap-c103a40ece` | INSERT CUSTOMER_MASTER (seed) | — | `03_seed_static.sql:77-98` | `ap-dbf1b410e9` (`trg_customer_master_hist`) | update/delete | same over-approximation |
| `ap-06d2eaab32` | INSERT…SELECT CUSTOMER_MASTER (upgrade) | — | `04_upgrade_static.sql:101-127` | `ap-dbf1b410e9` | update/delete | same over-approximation |

Over-approximation source: `access_scan.py` builds `events = {"insert","update"}`
for `INSERT`/`MERGE` verbs before intersecting with the trigger's events, so
every INSERT into SUBSCRIPTIONS / CUSTOMER_MASTER is linked to the
UPDATE/DELETE history triggers. Reviewer decides; nothing was changed.

No write in the scanned roots cascades to `trg_billing_audit_log_id`,
`trg_sub_no_uncancel`, `trg_customer_master_seq` or `trg_entity_attr_value_seq`
because those triggers have no row of their own (§7).

## 5. Every `drives_loop` / `current_of` / `in_loop` row

| Id | op / table | routine | source | flags |
|---|---|---|---|---|
| `ap-781940a6e5` | read SUBSCRIPTIONS | `pkg_plans.sp_change_plan` | `02_pkg_plans.sql:75-80` | `drives_loop` (cursor `c_open_subs`) |
| `ap-a7af1a6156` | write SUBSCRIPTIONS | `pkg_plans.sp_change_plan` | `02_pkg_plans.sql:91-94` | `current_of: "c_open_subs"`, `in_loop` |
| `ap-61c2839e36` | read USAGE_EVENTS | `pkg_rating.compute_rating` | `03_pkg_rating.sql:77-78` | `drives_loop` |
| `ap-81929b0d21` | read RATING_RESULTS ⋈ RATING_PERIODS | `pkg_rating.compute_rating` | `03_pkg_rating.sql:87-92` | `drives_loop` |
| `ap-2e59f9675d` | read CREDIT_NOTES | `pkg_invoicing.compute_preview` | `04_pkg_invoicing.sql:53-54` | `drives_loop` |
| `ap-56d46b7c81` | write INVOICE_LINES | `pkg_invoicing.sp_issue_invoice` | `04_pkg_invoicing.sql:157-163` | `in_loop` |
| `ap-b259650bfe` | read CREDIT_NOTES | `pkg_invoicing.sp_issue_invoice` | `04_pkg_invoicing.sql:182-184` | `drives_loop` |
| `ap-7a575dfc2d` | write CREDIT_NOTES | `pkg_invoicing.sp_issue_invoice` | `04_pkg_invoicing.sql:186-188` | `in_loop` |
| `ap-644c102b12` | read INVOICES | `pkg_dunning.sp_schedule_dunning` | `05_pkg_dunning.sql:40-42` | `drives_loop`, `invoked_by` job line 13, `schedule_hint: daily` |
| `ap-37287a11b5` | read DUNNING_ATTEMPTS | `pkg_dunning.sp_schedule_dunning` | `05_pkg_dunning.sql:43-44` | `in_loop` (per-invoice existence check) |
| `ap-68fdfcc880` | write DUNNING_ATTEMPTS | `pkg_dunning.sp_schedule_dunning` | `05_pkg_dunning.sql:53-58` | `in_loop` |
| `ap-eb72a29af5` | read INVOICES | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:74-77` | `drives_loop` |
| `ap-c089416cd9` | read TENANTS | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:78-79` | `in_loop` |
| `ap-8e4baaa9a0` | write TENANTS | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:81` | `in_loop` |
| `ap-d3754b6b8a` | write SUBSCRIPTIONS | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:82-84` | `in_loop`, cascades `ap-bdfdef0db0` |
| `ap-7692fe1e9a` | write NOTIFICATIONS (INSERT…SELECT) | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:86-94` | `in_loop` |
| `ap-cd2440f5ed` | read NOTIFICATIONS | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:87-94` | `in_loop`, nested in `ap-7692fe1e9a` |
| `ap-d0e6a55401` | read NOTIFICATIONS | `pkg_dunning.sp_suspend_overdue` | `05_pkg_dunning.sql:92-94` | `in_loop`, nested in `ap-cd2440f5ed` |

Only one `current_of` row exists (`ap-a7af1a6156`). The `in_loop` writes in
`sp_suspend_overdue` (`UPDATE tenants` / `UPDATE subscriptions` by `tenant_id`)
are keyed writes inside a cursor loop, not `CURRENT OF`.

## 6. `txn` and `identity_capture` rows

**None.** Neither key appears in any of the 86 candidates. In the pinned
scanner both are produced only by the T-SQL path (`_tsql_transaction_spans`,
`SCOPE_IDENTITY`/`OUTPUT INSERTED`); the Oracle path never emits them. Facts the
reviewer therefore does not get from the JSON:

- `pkg_ow_util.log_msg` — `PRAGMA AUTONOMOUS_TRANSACTION` (`01_pkg_util.sql:67`),
  `COMMIT` (`:72`), `WHEN OTHERS THEN ROLLBACK` (`:76`). Candidate `ap-779ce5b5b7`
  has no `txn`/`detached` marker. Scanner miss (unconfirmed).
- `JOB_PURGE_AUDIT_LOG` job text commits inside the block (`04_jobs.sql:24`,
  `… COMMIT; EXCEPTION WHEN OTHERS THEN NULL; END;`). `ap-e7b18e81b8` has no `txn`.
  Scanner miss (unconfirmed).
- Script-level `COMMIT;` at `01_tables.sql:38`, `02_horror.sql:20`,
  `03_seed_static.sql:121`, `04_upgrade_static.sql:179` — deploy scripts, not
  recorded; immaterial for access modelling.
- No `RETURNING … INTO` anywhere in `packages/` or `schema/`, so the missing
  `identity_capture` support costs nothing here. Sequence-driven identity is
  done in triggers instead (`seq_billing_audit_log.NEXTVAL` `01_tables.sql:184`,
  `seq_customer_master.NEXTVAL` `02_horror.sql:351`,
  `seq_entity_attr_value.NEXTVAL` `02_horror.sql:396`) and is not represented
  in any candidate (§7).

## 7. Census tables no candidate touches, and other coverage gaps

Untouched by **any** candidate (0 of 86):

- `INVOICE_HEADER` — created `02_horror.sql:429`; no DML in any scanned root.
- `INVOICE_LINE` — created `02_horror.sql:405`; no DML in any scanned root.

Per `ops/OPERATIONS_HANDBOOK.doc.txt:21-22` (unparsed) both are "loaded nightly
from the mainframe CUSTBILL feed", i.e. the writer is outside this repo; the
only in-repo filler is `testdata/legacy/oracle_billing_seed.py` (not a root).

Touched **only** by `deploy_script: true` candidates (no runtime caller in
`packages/`, triggers or jobs):

- `CUSTOMER_MASTER` — seed/upgrade INSERTs only (`ap-c103a40ece`, `ap-06d2eaab32`
  + nested reads).
- `ENTITY_ATTR_VALUE` — seed/upgrade INSERTs only (`ap-35915eb1a1`, `ap-a82c763f48`
  + nested reads).
- `FIXTURE_META` — `MERGE` in `04_upgrade_static.sql:170-177` (`ap-f84584cd2a`)
  only; the other writer is `startup/00_init.sh` (outside roots).

Write-only / read-only in the scanned roots (reviewer may want to know):

- `SUBSCRIPTIONS_HIST`, `CUSTOMER_MASTER_HIST` — written only by their triggers;
  never read.
- `BILLING_AUDIT_LOG` — written by `log_msg`, deleted by `JOB_PURGE_AUDIT_LOG`;
  never read in scanned roots (only the handbook's morning check, below).
- `CODES` — read by `f_code_desc` and `trg_usage_events_check`; written only by
  deploy DML.

## 8. Scanner misses (unconfirmed) — file:line for the reviewer

1. **Four of seven census triggers have no row at all**, because their bodies
   contain no DML against a census table (only `SELECT seq.NEXTVAL INTO :NEW.x
   FROM dual` or a pure `RAISE_APPLICATION_ERROR` rule):
   `trg_billing_audit_log_id` (`schema/01_tables.sql:179-186`, BEFORE INSERT ON
   BILLING_AUDIT_LOG), `trg_sub_no_uncancel` (`schema/01_tables.sql:228-235`,
   BEFORE UPDATE OF status_cd ON SUBSCRIPTIONS — rejects cancelled→active),
   `trg_customer_master_seq` (`schema/02_horror.sql:346-355`, BEFORE INSERT ON
   CUSTOMER_MASTER), `trg_entity_attr_value_seq` (`schema/02_horror.sql:391-398`,
   BEFORE INSERT ON ENTITY_ATTR_VALUE). Consequence: `ap-779ce5b5b7`
   (INSERT billing_audit_log), `ap-a7af1a6156` / `ap-d3754b6b8a` (UPDATE
   subscriptions.status_cd), `ap-c103a40ece` / `ap-06d2eaab32` (INSERT
   customer_master), `ap-35915eb1a1` / `ap-a82c763f48` (INSERT entity_attr_value)
   carry no `cascades` to these triggers, and the business rule in
   `trg_sub_no_uncancel` is invisible in the JSON. The census does list all
   seven triggers, so the names are recoverable from `census.json`.
2. **Cascade over-approximation on INSERT** (§4): six INSERT candidates are
   linked to AFTER UPDATE OR DELETE history triggers.
3. **`txn` never emitted for Oracle** (§6): `01_pkg_util.sql:67,72,76` and
   `04_jobs.sql:24`.
4. **`ops/` not parsed** (`.txt` extension). Statements in there the reviewer may
   want to classify by hand:
   - `ops/OPERATIONS_HANDBOOK.doc.txt:29` — `SELECT COUNT(*) FROM billing_audit_log
     WHERE log_ts > SYSDATE-1` (manual "morning check"; note the column is
     `logged_at` in the census, `log_ts` does not exist — the handbook SQL is
     stale).
   - `ops/OPERATIONS_HANDBOOK.doc.txt:21-22, 35, 43, 49` — prose naming the
     external CUSTBILL writer of INVOICE_HEADER/INVOICE_LINE, ad-hoc reads of
     INVOICE_LINE, orphan INVOICE_LINE rows, and the nightly dunning/CUSTBILL
     overlap. No SQL to extract, but it is the only evidence for the two
     untouched tables.
   - `ops/deploy_prod_FINAL_v2.sh.txt:29,34-35` — `sqlplus @$f` over the schema
     files and `DBMS_UTILITY.compile_schema`; no DML of its own.
5. **Repeated literal DML is de-duplicated** (id = hash of file + normalised
   statement), so the `source.lines` of a seed candidate points at the first
   occurrence only: `01_tables.sql` 22 `INSERT INTO codes` → 1 row at `:17`;
   `02_horror.sql` 12 → 1 row at `:9`; `03_seed_static.sql` 62 INSERTs → 14 rows
   (e.g. 10 `tenants` → `ap-872aee5734` at `:9`; 13 `usage_events` →
   `ap-27ea66fd68` at `:35`; the 4 `entity_attr_value` INSERTs at `:100-119`
   → `ap-35915eb1a1` at `:100-104`); `04_upgrade_static.sql` 13 INSERT + 1 MERGE
   → 22 rows (each `INSERT … SELECT … WHERE NOT EXISTS` yields a write + an
   outer read + a nested read). Nothing lost, but row counts per file are not
   statement counts.
6. **Intra-package call graph is not recorded**; `invoked_by` only carries
   scheduler-job callers. `pkg_rating.compute_rating` rows do not show that they
   run from `fn_usage_rating` (`03_pkg_rating.sql:126`), `sp_finalize_rating`
   (`:195`) and `pkg_invoicing.compute_preview` (`04_pkg_invoicing.sql:48`);
   `sp_issue_invoice` calls `pkg_rating.sp_finalize_rating` (`:134`) and
   `fn_invoice_preview` (`:152`), so an invoice issue transitively performs all
   `compute_rating` / `sp_finalize_rating` access. `log_msg` is called from
   every package.
7. **Dynamic SQL is captured but line-ranged to the literal**: `ap-875f85e898`
   (`02_pkg_plans.sql:101`) is an `EXECUTE IMMEDIATE` string concatenated across
   lines 101-102; `ap-5c6c87e418` (`04_pkg_invoicing.sql:150`) likewise. Bind
   positions render as `:?`.
8. **Job schedule precision**: `schedule_hint: "daily"` drops `BYHOUR=2`
   (`04_jobs.sql:15`) and `BYHOUR=3;BYMINUTE=30` (`:26`).
9. **`04_upgrade_static.sql:6-18`** — anonymous block over `user_tab_columns` +
   `EXECUTE IMMEDIATE 'ALTER TABLE …'`: DDL, not a census table, no candidate.
   Listed only so the reviewer knows it was seen and skipped on purpose.

## 9. Verification performed

- Pinned clone unchanged (`git -C ~/mmp rev-parse HEAD` =
  `353280fc837193a40ccc005cb62fb4ffaf8ac16f`, clean tree).
- `services/legacy-billing/db/oracle/` and `testdata/legacy/` untouched
  (`git status` shows only the two `.migration/` files).
- Output invariants checked: 86 patterns, all `confirmed: false`, all
  `frequency: null`, no `pinned` key, `census_sha256` matches `census.json`.
- `make tp-smoke` → `tp-smoke: all checks passed`.
