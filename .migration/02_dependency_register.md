# 02 — Dependency register: other readers, writers and scheduled logic

Plan step `s2.3-dependency-register` (phase: Census and data profile). Ticket UNT8-8.

| Run header | |
|---|---|
| Run branch | `tp-run/mongodb-20261007T161014Z` |
| Plugin under test | `Cognition-Partner-Workshops/mongo-migration-plugin` @ `353280fc837193a40ccc005cb62fb4ffaf8ac16f` (clone `~/mmp`, unpatched, nothing pushed) |
| Database access | none — this step is a static read of the run-branch sources listed below |
| Census basis | `.migration/census.json` / `01_census_crosscheck.md` (20 live tables incl. `FIXTURE_META`, 7 triggers, 10 PL/SQL units, 2 scheduler jobs) |
| Policy files | none edited (`allowed_targets.json`, `authorizations.json`, tolerances untouched) |

Inputs read (all under `services/legacy-billing/db/oracle/` unless stated): `README.md`, `schema/04_jobs.sql`,
`ops/OPERATIONS_HANDBOOK.doc.txt`, `ops/deploy_prod_FINAL_v2.sh.txt`, `setup/01_users.sql`, `startup/00_init.sh`,
`.agents/skills/oracle-billing-estate/SKILL.md`; plus the package / trigger bodies the jobs call
(`packages/01_pkg_util.sql`, `packages/05_pkg_dunning.sql`, `schema/01_tables.sql`, `schema/02_horror.sql`) so that
"tables written by that path" is cited, not inferred.

Disposition vocabulary: **access evidence** = must appear (and be confirmable) in `.migration/access_patterns.json`
for the proposer; **informational** = shapes operations/cutover but is not a modelling input; **out of scope** = not
read, by plan decision.

## 1. Scheduled logic — `DBMS_SCHEDULER` jobs (`schema/04_jobs.sql`)

Both jobs are created `enabled => FALSE` ("disabled deterministic baseline", `04_jobs.sql:1-5`; `README.md:91-94`
says they can be enabled manually). In the fixture they therefore never fire; the operations handbook treats them
as live nightly batch in production (`OPERATIONS_HANDBOOK.doc.txt:25-31`). Cadence below is the declared
`repeat_interval`.

| Object | Kind | Action (verbatim target) | Package procedure(s) called | Cadence | Disposition | Cited |
|---|---|---|---|---|---|---|
| `JOB_NIGHTLY_DUNNING` | job (`PLSQL_BLOCK`) | `BEGIN pkg_dunning.sp_schedule_dunning(TRUNC(SYSDATE)); pkg_dunning.sp_suspend_overdue(TRUNC(SYSDATE)); END;` | `pkg_dunning.sp_schedule_dunning`, `pkg_dunning.sp_suspend_overdue` | `FREQ=DAILY;BYHOUR=2;BYMINUTE=0` (02:00), disabled | access evidence (`cold`, schedule hint 02:00) | `schema/04_jobs.sql:8-17` |
| `JOB_PURGE_AUDIT_LOG` | job (`PLSQL_BLOCK`) | `BEGIN DELETE FROM billing_audit_log WHERE logged_at < SYSDATE - 90; COMMIT; EXCEPTION WHEN OTHERS THEN NULL; END;` | none — inline SQL, no package | `FREQ=DAILY;BYHOUR=3;BYMINUTE=30` (03:30), disabled | access evidence (`cold`; sole deleter of `BILLING_AUDIT_LOG`; 90-day retention hard-coded; errors swallowed) | `schema/04_jobs.sql:19-28` |

### 1.1 Tables touched by the `JOB_NIGHTLY_DUNNING` path

| Step | Table | R/W | Cited |
|---|---|---|---|
| `sp_schedule_dunning` | `INVOICES` | R (overdue by `p_as_of`) | `packages/05_pkg_dunning.sql:40-43` |
| | `DUNNING_ATTEMPTS` | R (existing attempts per invoice) | `packages/05_pkg_dunning.sql:44` |
| | `DUNNING_ATTEMPTS` | **W** INSERT | `packages/05_pkg_dunning.sql:53-64` |
| | `BILLING_AUDIT_LOG` | **W** INSERT via `pkg_ow_util.log_msg` (`PRAGMA AUTONOMOUS_TRANSACTION`, own COMMIT → `detached`) | `packages/05_pkg_dunning.sql:66`; `packages/01_pkg_util.sql:66-72` |
| `sp_suspend_overdue` | `INVOICES` | R (overdue tenants) | `packages/05_pkg_dunning.sql:74-78` |
| | `TENANTS` | R (`status_cd = 10`) then **W** UPDATE `status_cd = 20` | `packages/05_pkg_dunning.sql:79-81` |
| | `SUBSCRIPTIONS` | **W** UPDATE status → fires `TRG_SUBSCRIPTIONS_HIST` (**W** `SUBSCRIPTIONS_HIST`) and `TRG_SUB_NO_UNCANCEL` | `packages/05_pkg_dunning.sql:82-85`; `schema/01_tables.sql:206-236` |
| | `NOTIFICATIONS` | R (dedupe `NOT EXISTS`) then **W** INSERT | `packages/05_pkg_dunning.sql:86-95` |
| | `BILLING_AUDIT_LOG` | **W** INSERT via `log_msg` (detached) → fires `TRG_BILLING_AUDIT_LOG_ID` | `packages/05_pkg_dunning.sql:96`; `schema/01_tables.sql:179-187` |

Net: the nightly job **writes** `DUNNING_ATTEMPTS`, `TENANTS`, `SUBSCRIPTIONS` (+ `SUBSCRIPTIONS_HIST` via trigger),
`NOTIFICATIONS`, `BILLING_AUDIT_LOG`; **reads** `INVOICES`. Every one of those tables is also written by an
application-driven package entry point (`sp_change_plan`, `sp_issue_invoice`, `log_msg` callers) or the app itself
(§7, O-1), so no table is written *only* by a job.

### 1.2 Tables touched by the `JOB_PURGE_AUDIT_LOG` path

| Table | R/W | Cited |
|---|---|---|
| `BILLING_AUDIT_LOG` | R (`logged_at < SYSDATE - 90`) then **W** DELETE + COMMIT | `schema/04_jobs.sql:22` |

This job is the **only** `DELETE` against `BILLING_AUDIT_LOG` anywhere in the estate; everything else only inserts
(`log_msg`). See O-5.

## 2. Operational scripts (`ops/`)

| Object | Kind | What it reads / writes | Deploy-time or recurring | Disposition | Cited |
|---|---|---|---|---|---|
| `OPERATIONS_HANDBOOK.doc.txt` §"Daily operations" | ops runbook | Describes the 02:00 dunning/suspension job and 03:30 audit purge (same objects as §1); a **morning manual `COUNT(*)` on `BILLING_AUDIT_LOG`** (R) by the DBA — written against a column `log_ts` that does not exist (the table has `logged_at`, `schema/01_tables.sql:169-175`), so the documented check cannot run as printed | recurring (daily) | informational — restates §1; the manual count is a human read, not an application pattern; the column drift is a documentation defect, not a modelling input | `ops/OPERATIONS_HANDBOOK.doc.txt:25-31` |
| `OPERATIONS_HANDBOOK.doc.txt` §"Month-end" | ops runbook | Freeze: no DML on `INVOICE_LINE` while the month-end run is in flight | recurring (monthly) | informational — a cutover/scheduling constraint for the `INVOICE_HEADER`/`INVOICE_LINE` wave, not an access pattern | `ops/OPERATIONS_HANDBOOK.doc.txt:33-37` |
| `OPERATIONS_HANDBOOK.doc.txt` §"Known issues" | ops runbook | Nightly dunning job overlaps the **CUSTBILL load** window; names `CUSTOMER_MASTER`, `ENTITY_ATTR_VALUE`, `INVOICE_HEADER`, `INVOICE_LINE` as the system-of-record tables | recurring | informational; CUSTBILL itself is an open item (O-3) | `ops/OPERATIONS_HANDBOOK.doc.txt:12-23, 38-50` |
| `OPERATIONS_HANDBOOK.doc.txt` §"Restore" | ops runbook | intentionally blank | — | informational (no restore procedure exists) | `ops/OPERATIONS_HANDBOOK.doc.txt:60-62` |
| `deploy_prod_FINAL_v2.sh.txt` | ops script (ksh, inert `.txt`; "not executable", demo artifact) | **R** full `exp` export of owner `OW_BILLING` to `/u01/backup/pre_${RELEASE}.dmp`; stops/starts `appadmin` services on `owbillapp01/02`; **W** runs every `/u01/releases/${RELEASE}/*.sql` alphabetically as `OW_BILLING`, continuing past SQL errors; recompiles the `OW_BILLING` schema up to 3×; smoke test is a `TODO` | deploy-time only, run manually in the 02:20–02:55 quiet window (after dunning, before purge) | informational (`deploy_script: true`); the wildcard `*.sql` means its table footprint is **not statically enumerable** — O-4 | `ops/deploy_prod_FINAL_v2.sh.txt:1-14, 16-20, 22-25, 27-30, 32-37, 39-48` |

No ops script in `ops/` performs recurring application DML. The handbook's recurring items are the §1 jobs plus one
manual read.

## 3. Triggers (7, matches census `plsql_objects`)

All triggers are row-level and fire synchronously inside the writer's transaction (`written_together`, not
standalone). The proposer needs the `cascades` edge on the *parent write*; that is what `s3.1`/`s3.2` must confirm.

| Object | Kind | Table (event) | Reads | Writes | Cadence | Disposition | Cited |
|---|---|---|---|---|---|---|---|
| `TRG_BILLING_AUDIT_LOG_ID` | trigger | `BILLING_AUDIT_LOG` (BEFORE INSERT) | sequence | `:NEW.id` on `BILLING_AUDIT_LOG` | every insert (every `log_msg` call) | access evidence (identity capture) | `schema/01_tables.sql:179-187` |
| `TRG_SUBSCRIPTIONS_HIST` | trigger | `SUBSCRIPTIONS` (AFTER UPDATE OR DELETE) | `:OLD` row | **W** INSERT `SUBSCRIPTIONS_HIST` (old version) | every subscription update/delete (`sp_change_plan`, `sp_suspend_overdue`, app `change_plan`) | access evidence — `SUBSCRIPTIONS_HIST` has **no other writer**; must surface as `via_trigger` / `written_together` | `schema/01_tables.sql:206-224` |
| `TRG_SUB_NO_UNCANCEL` | trigger | `SUBSCRIPTIONS` (BEFORE UPDATE OF `STATUS_CD`) | `:OLD.status_cd` | forces cancelled rows to stay cancelled (overrides `:NEW.status_cd`) | every status update | access evidence (business rule to port, no table write) | `schema/01_tables.sql:228-236` |
| `TRG_USAGE_EVENTS_CHECK` | trigger | `USAGE_EVENTS` (BEFORE INSERT) | `CODES` (`USAGE_KIND`) | none — raises on `units <= 0` / unknown kind | every usage insert | access evidence (validation read on `CODES`; rule to port) | `schema/01_tables.sql:239-254` |
| `TRG_CUSTOMER_MASTER_SEQ` | trigger | `CUSTOMER_MASTER` (BEFORE INSERT) | sequence | `:NEW.cust_seq_no`, `cust_name_upper`, `row_version` defaults | every insert | access evidence (identity capture + derived column) | `schema/02_horror.sql:346-356` |
| `TRG_CUSTOMER_MASTER_HIST` | trigger | `CUSTOMER_MASTER` (AFTER UPDATE OR DELETE) | `:OLD` full row (158 cols) | **W** INSERT `CUSTOMER_MASTER_HIST` | every update/delete — **no in-estate path updates `CUSTOMER_MASTER`**, live count 0 | access evidence, but unexercised — O-6 | `schema/02_horror.sql:358-374`; `01_census_crosscheck.md` §6 |
| `TRG_ENTITY_ATTR_VALUE_SEQ` | trigger | `ENTITY_ATTR_VALUE` (BEFORE INSERT) | sequence | `:NEW` id | every insert | access evidence (identity capture) | `schema/02_horror.sql:391-399` |

## 4. Principals and grants (`setup/01_users.sql`)

| Object | Kind | Grants / role | Tables touched | Cadence | Disposition | Cited |
|---|---|---|---|---|---|---|
| `OW_BILLING` | principal (schema owner) | `CREATE SESSION, CREATE TABLE, CREATE SEQUENCE, CREATE PROCEDURE, CREATE TRIGGER, CREATE VIEW, CREATE TYPE, CREATE JOB`; `QUOTA UNLIMITED ON users` | owns every census table; all packages, triggers and both jobs run as this user | created once at boot (dropped and recreated if present) | informational — single-principal model: the app (`docker-compose.tp.yml` `ORACLE_USER` default `ow_billing`), the CUSTBILL extract, the seeder and the deploy script all connect as the owner; there is **no read-only or app-scoped principal** to mirror in Atlas roles — O-7 | `setup/01_users.sql:5-8`; `docker-compose.tp.yml:14-17` |
| `SYSTEM` | principal (admin, container-internal) | runs `01_users.sql` as SYSTEM inside `FREEPDB1` | none in-schema | boot only | informational | `setup/01_users.sql:1-3`; `startup/00_init.sh:94-111` |

No other users, roles, synonyms, or cross-schema grants are created anywhere in the Oracle sources.

## 5. Boot path (`startup/00_init.sh`) — what the container executes

Deploy-time only (container first start; idempotent repair on restart). `run_sql(conn, file)` runs each file through
SQL*Plus as the principal passed in (`00_init.sh:20-23`): `SYSTEM` for the `FIXTURE_META` / user / invalid-object
probes and `setup/01_users.sql` (`00_init.sh:26, 36, 70, 94-110, 125-136`), `OW_BILLING` for everything else
(`00_init.sh:49-50, 81, 113-121, 148, 167`). Disposition for the whole path: **informational / `deploy_script: true`** — it
creates the estate and seeds fixture rows; it is not an application access pattern.

| Order | Executes | Effect | Cited |
|---|---|---|---|
| 1 | `FIXTURE_META` check/repair; if already initialised, re-apply `schema/04_upgrade_static.sql` only | R/W `FIXTURE_META` (bookkeeping table; the only table not in the DDL census) | `00_init.sh:26-92` |
| 2 | `setup/01_users.sql` (create or drop+recreate `OW_BILLING`) | principal (§4) | `00_init.sh:94-111` |
| 3 | `schema/01_tables.sql`, `schema/02_horror.sql` | all tables, sequences, 7 triggers | `00_init.sh:113-121` |
| 4 | `packages/01_pkg_util.sql` … `04_pkg_invoicing.sql`, `schema/03_seed_static.sql`, `packages/05_pkg_dunning.sql`, `schema/04_jobs.sql` | 10 PL/SQL units; static seed **W** into `TENANTS, PLANS, SUBSCRIPTIONS, USAGE_EVENTS, RATING_PERIODS, RATING_RESULTS, INVOICES, INVOICE_LINES, DUNNING_ATTEMPTS, NOTIFICATIONS, CREDIT_NOTES, CUSTOMER_MASTER, ENTITY_ATTR_VALUE`; both jobs created disabled | `00_init.sh:113-121`; `schema/03_seed_static.sql` |
| 5 | invalid-object check (fails the boot if any `INVALID`) | R `user_objects` | `00_init.sh:123-144` |
| 6 | `FIXTURE_META` MERGE, then `schema/04_upgrade_static.sql` (idempotent upserts of static rows) | **W** `FIXTURE_META` + static rows | `00_init.sh:146-167` |

Per-namespace data arrives later through `make oracle-billing-seed NS=<ns>` → `testdata/legacy/oracle_billing_seed.py`
(read-only for this run; see O-2).

## 6. Out of scope by plan decision

`services/legacy-billing/db/procs/` is the **PostgreSQL parallel port** of the billing procedures (the
`procs-parity` / `stored-procs-to-microservices` track). It is not an Oracle caller, reader or writer. Per the intake
and this ticket it is **out of scope** for the Oracle → Atlas migration: it was **not scanned** for this register and
must not be added as an `access_scan.py --root` in `s3.1`. Nothing in `04_jobs.sql`, `ops/`, `setup/` or `startup/`
references it.

## 7. Open items for the manager — things the intake did not mention

The intake states that the jobs, ops scripts, principals, boot path, packages and triggers are the **only**
readers/writers. Reading the handbook's own references (CUSTBILL, the app) and the run-branch tree turned up the
following additional Oracle readers/writers. None is in the `s3.1` scan roots (`packages`, `schema`, `ops`), so
without a decision they will be absent from `access_patterns.json`.

| # | Finding | Tables | Kind / cadence | Why it matters | Cited |
|---|---|---|---|---|---|
| **O-1** | The legacy-billing **application issues direct DML outside the packages**: `ensure_tenant` inserts `TENANTS` and `SUBSCRIPTIONS`; `change_plan` runs an `UPDATE subscriptions` *before* calling `pkg_plans.sp_change_plan`; the internal usage endpoint inserts `USAGE_EVENTS`. **`USAGE_EVENTS` has no writer in any package, job or trigger** — the app (and the seeders) are its only writers. The facade also reads `TENANTS`, `CODES`, `CUSTOMER_MASTER`, `ENTITY_ATTR_VALUE`, `USAGE_EVENTS`, `INVOICES`, `RATING_PERIODS`, `DUNNING_ATTEMPTS` directly. | W: `TENANTS`, `SUBSCRIPTIONS` (+`SUBSCRIPTIONS_HIST` via trigger), `USAGE_EVENTS`; R: as listed | app code, per request (`warm`/`hot`) | Access evidence the proposer will not see unless `s3.1` adds `--root services/legacy-billing/app` (or the manager records these patterns by hand in `s3.2`). Decision needed. | `services/legacy-billing/app/backends/oracle.py:64-81, 134-171`; `services/legacy-billing/app/facade.py:98-135, 197-230, 231-303, 327-355, 356-412` |
| **O-2** | **`CUSTOMER_MASTER`, `CUSTOMER_MASTER_HIST`, `ENTITY_ATTR_VALUE`, `INVOICE_HEADER`, `INVOICE_LINE` have no in-estate writer**: no package, job or ops script inserts/updates them; the only writers are the static seed / upgrade scripts (boot) and the namespace seeder `testdata/legacy/oracle_billing_seed.py` (W `CUSTOMER_MASTER`, `ENTITY_ATTR_VALUE`, `INVOICE_HEADER`, `INVOICE_LINE`, `TENANTS`, `SUBSCRIPTIONS`, `USAGE_EVENTS`, deletes per namespace first). | as listed | fixture seeder, deploy/fixture-time | For the proposer these five tables are **read-only in production code**; the mapping spec should treat them as such (no `written_together` evidence will exist). Confirm this is the intended reading of "system of record" (`OPERATIONS_HANDBOOK.doc.txt:12-23`). | `testdata/legacy/oracle_billing_seed.py` (read-only for this run); `schema/03_seed_static.sql`; `schema/04_upgrade_static.sql` |
| **O-3** | The **CUSTBILL feed** the handbook names is real code: `etl/legacy-extra/tools/oracle_custbill_extract.py` reads `INVOICE_HEADER ⋈ CUSTOMER_MASTER ⋈ TENANTS` (filtered by `conversion_batch_no` / admin tenant) and writes a flat file; `services/legacy-billing/app/reports.py` reads `INVOICE_HEADER`, `INVOICE_LINE`, `CODES`, `CUSTOMER_MASTER` for the month-end / status / reconciliation reports. Both run via `make tp-month-end NS=<ns>`. | R only: `INVOICE_HEADER`, `INVOICE_LINE`, `CUSTOMER_MASTER`, `TENANTS`, `CODES` | ETL / reporting, monthly (`cold`) | Downstream **readers** not in the intake; they must be repointed (or fed from Atlas) at cutover and are the join-shape evidence for the `INVOICE_HEADER`→`INVOICE_LINE` and `CUSTOMER_MASTER` decisions. | `etl/legacy-extra/tools/oracle_custbill_extract.py:93-114`; `services/legacy-billing/app/reports.py:40-92`; `Makefile:637-646` |
| **O-4** | `deploy_prod_FINAL_v2.sh.txt` applies **arbitrary `*.sql` release files** and continues on error; its write set cannot be enumerated statically. | unknown | deploy-time, manual | Not a modelling input, but the "continues past SQL errors" + 3× recompile pattern is a cutover risk the handbook does not flag. | `ops/deploy_prod_FINAL_v2.sh.txt:27-37` |
| **O-5** | `BILLING_AUDIT_LOG` retention lives **only** in a disabled scheduler job (90 days, hard-coded, errors swallowed). Writers are autonomous-transaction inserts (`detached`). | `BILLING_AUDIT_LOG` | daily (if enabled) | Atlas equivalent is a TTL index / capped collection decision for `d-*`; also, since the job is disabled in the fixture, there is no retention evidence to reconcile against. | `schema/04_jobs.sql:19-28`; `packages/01_pkg_util.sql:66-72` |
| **O-6** | `TRG_CUSTOMER_MASTER_HIST` **never fires** on this fixture (no path updates `CUSTOMER_MASTER`; live `CUSTOMER_MASTER_HIST` = 0). Already recorded as a UNT8-2 manager decision; re-flagged here because it means the `CUSTOMER_MASTER → CUSTOMER_MASTER_HIST` cascade will grade UNVERIFIED in recon. | `CUSTOMER_MASTER_HIST` | n/a | Either accept UNVERIFIED for this table or authorise one controlled update in a later step (would need `legacy_write_authorized`; not this ticket). | `schema/02_horror.sql:358-374`; `01_census_crosscheck.md` §6 |
| **O-7** | **Single principal**: everything (app, ETL, seeder, deploy, jobs) runs as the schema owner `OW_BILLING`; no reader/app role exists to translate into Atlas database roles. | all | — | Atlas role design (`s1.3-allowlist` / access-model step) starts from zero; the security reviewer should know there is no existing least-privilege split to preserve. | `setup/01_users.sql:5-8`; `docker-compose.tp.yml:14-17`; `etl/legacy-extra/tools/oracle_custbill_extract.py:98-104` |
| **O-8** | Both jobs are **disabled** (`enabled => FALSE`); the handbook describes them as running nightly. Fixture cadence ≠ documented production cadence. | §1 tables | — | `s3.2` frequency judgements (`cold` + schedule hint) must be labelled as taken from the handbook, not observed. | `schema/04_jobs.sql:15, 26`; `README.md:91-94`; `ops/OPERATIONS_HANDBOOK.doc.txt:25-31` |
| **O-9** | Read-only demo tooling touches the estate: `scripts/tp_pain/mongodb.py` (via `make tp-pain-mongodb`) runs `SELECT`s against `CUSTOMER_MASTER`, `CUSTOMER_MASTER_HIST`, `ENTITY_ATTR_VALUE`, `user_tab_columns`. | R only | ad hoc | informational — not a production reader; listed for completeness so nobody mistakes it for one. | `scripts/tp_pain/mongodb.py:1-20, 107-171` |
| **O-10** | The pinned profile's `dependencies` discovery query (`all_dependencies`, `~/mmp/skills/mongo-migration/profiles/oracle.md:97-99`) is reserved for this step but was **not run** (ticket: no database access). | — | — | Optional live cross-check in a later DB-connected step if the manager wants catalog confirmation of the package→table edges cited above. | `~/mmp/skills/mongo-migration/profiles/oracle.md:97-99` |

## 8. Coverage statement

- Read: every file named by the ticket, every package/trigger body those paths call, `docker-compose.tp.yml`,
  `Makefile` targets that invoke Oracle, and the app/ETL files the handbook's references led to.
- Not read: `services/legacy-billing/db/procs/` (§6, by decision); anything under `tech-partnerships-solutions`
  (not a correctness reference per branch policy).
- No `.migration/` policy file, no legacy source, no seeder and no plugin file was modified. No database connection
  was opened. No secret value appears in this document.
