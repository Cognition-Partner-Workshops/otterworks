# OW_BILLING access patterns (plan step `s2.2-access-patterns`)

How the legacy billing application uses the Oracle `OW_BILLING` estate: every
`services/legacy-billing/app/backends/oracle.py` entrypoint mapped to the PL/SQL
it calls, the tables it reads and writes, the join shapes, and the transaction
boundary the application actually commits. This feeds the embed/reference
decisions in the next step; it makes no target-model decision itself.

Method: static read of the Oracle backend, the HTTP surfaces that call it
(`facade.py`, `app.py`, `reports.py`, the usage bridge), the five PL/SQL
packages, the triggers and the scheduler jobs, cross-checked against the live
census (`migration/billing/census.json`, captured 2026-10-02T01:03:11Z from the
read-only principal; `dependencies.internal` is `DBA_DEPENDENCIES`). Oracle was
not written to. Cites are `path:line` relative to the repo root;
`migration/billing/access_patterns/check.py` verifies that every cite resolves
and that the per-package table sets below equal the census dependency edges
(the one deliberate gap, `CODES` via dynamic SQL, is listed in section 5).

## 1. Call surfaces and transaction primitives

Three ways into Oracle, all through `oracle_connect()`
(`services/legacy-billing/app/oracle_conn.py:8-15`, one new connection per
call, autocommit off):

| Primitive | Cite | Transaction behaviour |
|---|---|---|
| `query(sql, params)` | `services/legacy-billing/app/backends/oracle.py:34-38` | plain SELECT, no commit; connection closed on exit |
| `_function(name, args)` | `services/legacy-billing/app/backends/oracle.py:40-44` | `callfunc` returning `SYS_REFCURSOR`, **no commit**. Any write a "read" function does is lost unless it is autonomous (only `pkg_ow_util.log_msg` is) |
| `_procedure(name, args)` | `services/legacy-billing/app/backends/oracle.py:46-49` | `callproc` then **one `commit()`**. No package procedure contains `COMMIT`/`ROLLBACK`, so each procedure call is exactly one transaction; an exception leaves the connection uncommitted and it is rolled back on close |
| `change_plan` (hand-rolled) | `services/legacy-billing/app/backends/oracle.py:64-80` | UPDATE + `callproc` + one commit on one connection |
| `ensure_tenant(connection, ...)` | `services/legacy-billing/app/backends/oracle.py:134-169` | caller's connection; INSERT tenants + INSERT subscriptions + commit, `rollback()` on `IntegrityError` (`:146`, `:167`) |
| `pkg_ow_util.log_msg` | `services/legacy-billing/db/oracle/packages/01_pkg_util.sql:66-77` | `PRAGMA AUTONOMOUS_TRANSACTION` (`:67`): INSERT into `billing_audit_log` commits on its own (`:70-72`), `WHEN OTHERS THEN ROLLBACK` (`:76`) swallows failures. Its rows survive a rollback of the enclosing business transaction |

Who calls the backend:

- Facade `/api/v1/billing/*` (gateway route `services/api-gateway/internal/config/config.go:115`;
  contract route list `docs/tech-partnerships/contracts/billing-facade.contract.json`),
  `services/legacy-billing/app/facade.py`. Nearly every tenant route first runs
  `_ensure(tenant_id)` (`services/legacy-billing/app/facade.py:43-50`), a lazy
  tenant bootstrap write.
- Legacy UI / ops routes in `services/legacy-billing/app/app.py:23-95` (`/plans`,
  `/api/rating/*`, `/api/invoices/*`, `/api/dunning/*`) via `get_backend()`.
  These are the only HTTP callers of `finalize_rating`, `invoice_preview`,
  `issue_invoice`, `schedule_dunning` and `suspend_overdue`.
- Usage bridge: SQS -> `POST /internal/usage/events`
  (`services/legacy-billing/bridge/bridge.py:20`, `:202-207`), the only
  high-frequency writer.
- Scheduler: `JOB_NIGHTLY_DUNNING` runs `sp_schedule_dunning` then
  `sp_suspend_overdue` in one PL/SQL block (`services/legacy-billing/db/oracle/schema/04_jobs.sql:10-17`);
  `JOB_PURGE_AUDIT_LOG` deletes audit rows older than 90 days (`:21-28`). Both
  are created `enabled => FALSE` in the fixture (`:16`, `:27`).
- Finance reports (`services/legacy-billing/app/reports.py`) read only the
  denormalised "horror" tables; see section 4.

Oracle-only parity harness mapping of the same twelve entrypoints:
`procs/oracle/oracle_map.yaml:12-23`; Postgres-to-Oracle signature table:
`services/legacy-billing/db/oracle/README.md:51-69`.

## 2. Entrypoint map

Legend: R = read, W = write, `⋈` inner join, `⟕` left outer join (`(+)`),
`A` = autonomous audit write (`billing_audit_log`, committed independently).
"Txn" is the boundary the application commits, not what the PL/SQL declares.

### 2.1 `list_plans()` -> `pkg_plans.fn_list_plans`

- Backend `services/legacy-billing/app/backends/oracle.py:56-57` (`_function`).
- PL/SQL `services/legacy-billing/db/oracle/packages/02_pkg_plans.sql:20-33`.
- R `plans` (`:29`, `active_yn = 'Y'`, ordered by `monthly_fee, code`); tier
  decoded inline with `DECODE`, not a `codes` join (`:26`).
- W(A) `billing_audit_log` via `log_msg('PLANS', 'fn_list_plans')` (`:23`):
  **every plan listing writes an audit row**, even though `_function` never
  commits.
- Joins: none. Txn: read-only + autonomous audit.
- Callers: facade `GET /plans` (`services/legacy-billing/app/facade.py:72-94`),
  plan-change validation (`:177`), `app.py` `/` and `/plans`
  (`services/legacy-billing/app/app.py:23-31`).

### 2.2 `entitlement(tenant_id, on)` -> `pkg_plans.fn_entitlement`

- Backend `services/legacy-billing/app/backends/oracle.py:60-61`.
- PL/SQL `services/legacy-billing/db/oracle/packages/02_pkg_plans.sql:35-70`.
- R `tenants`, `subscriptions`, `plans`. Two statements:
  1. `subscriptions ⟕ plans` (`p.id (+) = s.plan_id`, `:41-47`) with
     `ROWNUM = 1` and no `ORDER BY` into package global `g_last_plan_code`
     (cached state, nondeterministic row; `WHEN OTHERS THEN NULL`).
  2. The result cursor: `tenants ⋈ subscriptions` on `s.tenant_id = t.id`,
     `subscriptions ⟕ plans` (`:61-63`), covering filter
     `starts_on <= p_on AND (ends_on IS NULL OR ends_on >= p_on)`, latest
     `starts_on` wins, `ROWNUM <= 1` (`:68`). Tenant and subscription status
     decoded inline.
- W: none. Txn: read-only.
- Callers: facade `GET /me` (`services/legacy-billing/app/facade.py:97-135`, which
  also runs ad-hoc `tenants ⟕ codes('TENANT_STATUS')` `:110-119` and the
  first `customer_master` row by `cust_seq_no` `:120-128`), `GET /entitlement`
  (`:137-151`), read-after-write in `POST /plan-change` (`:187-190`),
  `app.py` `/plans/<tenant_id>/entitlement` (`services/legacy-billing/app/app.py:33-36`).
- Shape note: tenant -> current subscription -> plan is the hottest read path
  (every facade tenant request).

### 2.3 `change_plan(tenant_id, plan_id, effective_on)` -> `pkg_plans.sp_change_plan`

- Backend `services/legacy-billing/app/backends/oracle.py:64-80`: on **one
  connection** (1) direct `UPDATE subscriptions` closing a same-day
  subscription (`ends_on = eff - 1`, `status_cd = DECODE(status_cd,30,30,10)`
  where `ends_on IS NULL AND starts_on = eff`, `:68-75`), (2)
  `callproc pkg_plans.sp_change_plan` (`:76-79`), (3) `commit()` (`:80`).
  Regression test: `services/legacy-billing/tests/test_oracle.py:88`.
- PL/SQL `services/legacy-billing/db/oracle/packages/02_pkg_plans.sql:72-105`:
  cursor over open subscriptions (`ends_on IS NULL AND starts_on < p_effective_on`)
  **`FOR UPDATE`** (`:76-80`, row locks held to the commit); per-row
  `UPDATE ... WHERE CURRENT OF` closing them (`:91-94`); deterministic new id
  `f_md5_uuid(tenant||plan||eff)` (`:97-98`); `EXECUTE IMMEDIATE INSERT INTO
  subscriptions` with `status_cd = 10` (`:101-104`).
- R `subscriptions` (locked). W `subscriptions` (UPDATE x N, INSERT x 1),
  `plans` validated only by `fk_sub_plan` (`services/legacy-billing/db/oracle/schema/01_tables.sql:71`).
- Trigger side effects on each UPDATE: `trg_sub_no_uncancel` (BEFORE UPDATE OF
  status_cd, raises if a cancelled row leaves 30, `:228-236`) and
  `trg_subscriptions_hist` (AFTER UPDATE OR DELETE, full-row copy into
  `subscriptions_hist`, `:206-224`).
- W(A) `billing_audit_log` (`02_pkg_plans.sql:84`).
- **Atomic unit:** same-day close-out + close-outs + new subscription +
  history rows, one commit. Not idempotent: repeating the same
  `(tenant, plan, eff)` hits `pk_subscriptions` (deterministic id) and the whole
  transaction rolls back.
- Callers: facade `POST /plan-change` (`services/legacy-billing/app/facade.py:154-193`,
  preceded by `list_plans` and `_ensure` on separate connections), `app.py`
  `/plans/<tenant_id>/change` (`services/legacy-billing/app/app.py:38-42`).

### 2.4 `usage_rating(tenant, start, end)` -> `pkg_rating.fn_usage_rating`

- Backend `services/legacy-billing/app/backends/oracle.py:83-87`.
- PL/SQL `services/legacy-billing/db/oracle/packages/03_pkg_rating.sql:122-140`
  -> `compute_rating` (`:32-120`), result projected from package globals via
  `SELECT ... FROM dual`.
- `compute_rating` reads:
  - `subscriptions`: latest covering subscription for the period,
    `ORDER BY starts_on DESC ... ROWNUM <= 1` (`:56-63`);
  - `plans` by `id` (`:69-70`);
  - `usage_events`: **all rows for the tenant** (`WHERE u.tenant_id = :t`),
    period filter applied row-by-row in PL/SQL with `TO_CHAR(...,'YYYYMMDD')`
    string compares (`:77-83`) -- a full per-tenant scan on every call;
  - `rating_results ⋈ rating_periods` on `rp.id = rr.period_id`, prior three
    months (`rp.period_start < start AND >= ADD_MONTHS(start,-3)`, `:86-93`)
    for rollover.
- W(A) `billing_audit_log` (`:117`): every rating read writes an audit row.
- Joins: one `rating_results ⋈ rating_periods`; the rest are point lookups.
- Txn: read-only + autonomous audit. Package-global state (`g_*`) persists for
  the session; each `_function` call is a fresh connection so no cross-call
  leakage in the app, but `fn_usage_rating` is only correct right after its own
  `compute_rating`.
- Callers: facade `GET /usage` (`services/legacy-billing/app/facade.py:196-227`,
  `:210`), `app.py` `/api/rating/preview` (`services/legacy-billing/app/app.py:44-48`).

### 2.5 `usage_summary(tenant, start, end)` -> `pkg_rating.fn_usage_summary`

- Backend `services/legacy-billing/app/backends/oracle.py:90-94`.
- PL/SQL `services/legacy-billing/db/oracle/packages/03_pkg_rating.sql:142-160`.
- R `usage_events` (`:151`), tenant + half-open period, `GROUP BY` decoded
  `kind_cd` (inline `DECODE`, no `codes` join), `COUNT(*)`, `SUM(units)`.
- W: none. Txn: read-only.
- Callers: facade `GET /usage` (`services/legacy-billing/app/facade.py:209`),
  which also runs ad-hoc `usage_events ⋈ codes('USAGE_KIND')`, newest 50
  (`:211-223`).

### 2.6 `finalize_rating(tenant, start, end)` -> `pkg_rating.sp_finalize_rating`

- Backend `services/legacy-billing/app/backends/oracle.py:97-101` (`_procedure`,
  commit at `:49`).
- PL/SQL `services/legacy-billing/db/oracle/packages/03_pkg_rating.sql:162-217`:
  1. R `subscriptions` covering subscription (`:172-178`, `NULL` if none);
  2. W `rating_periods` upsert: `INSERT` (`:185`, id `f_md5_uuid(tenant||start)`),
     `WHEN DUP_VAL_ON_INDEX` -> `UPDATE period_end` (`:188-191`), keyed by
     `uq_rating_periods (tenant_id, period_start)` (`services/legacy-billing/db/oracle/schema/01_tables.sql:84-92`);
  3. `compute_rating` (`:195`; reads as in 2.4);
  4. W `rating_results` upsert: `INSERT` (`:199`, id `f_md5_uuid(period_id)`),
     `WHEN DUP_VAL_ON_INDEX` -> `UPDATE` (`:208-214`).
- W(A) `billing_audit_log` (`:216`, plus one from `compute_rating`).
- **Atomic unit:** period upsert + result upsert, one commit. If no covering
  subscription exists, `rating_results.subscription_id NOT NULL`
  (`services/legacy-billing/db/oracle/schema/01_tables.sql:97`) fails the INSERT and the
  period upsert rolls back with it. Idempotent on rerun (upserts).
- Callers: `app.py` `/api/rating/finalize` (`services/legacy-billing/app/app.py:50-55`)
  only, and `sp_issue_invoice` (2.8). Not on the facade.

### 2.7 `invoice_preview(tenant, start, end)` -> `pkg_invoicing.fn_invoice_preview`

- Backend `services/legacy-billing/app/backends/oracle.py:104-108`.
- PL/SQL `services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql:71-100`
  -> `compute_preview` (`:28-69`) -> `pkg_rating.compute_rating` (`:48`).
- `compute_preview` reads: `subscriptions ⋈ plans` (`p.id = s.plan_id`, inner,
  covering + latest, `ROWNUM <= 1`, `:35-43`); `credit_notes` with
  `remaining_amount > 0` summed in a cursor loop (`:53-56`); `tenants.tax_exempt_yn`
  (`:59-60`); plus everything `compute_rating` reads (2.4).
- Output: five synthetic lines (plan, usage, tax, credit) `UNION ALL` from
  `dual`, driven by package globals.
- W(A) `billing_audit_log` (through `compute_rating`). Txn: read-only.
- Callers: `app.py` `/api/invoices/<tenant_id>/preview`
  (`services/legacy-billing/app/app.py:57-64`) and `sp_issue_invoice`. Not on the facade.

### 2.8 `issue_invoice(tenant, start, end)` -> `pkg_invoicing.sp_issue_invoice`

- Backend `services/legacy-billing/app/backends/oracle.py:111-115` (`_procedure`,
  single commit at `:49`).
- PL/SQL `services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql:113-194`,
  in order inside **one database transaction**:
  1. ids: `period_id = f_md5_uuid(tenant||start)`,
     `invoice_id = f_md5_uuid(period_id||'invoice')` (`:130-132`);
  2. `pkg_rating.sp_finalize_rating` (`:134`): W `rating_periods`, `rating_results` (2.6);
  3. W `invoices` header `INSERT` (`:137-142`), `WHEN DUP_VAL_ON_INDEX` ->
     `UPDATE invoices SET status_cd = 20` (`:144-145`);
  4. W `invoice_lines` `EXECUTE IMMEDIATE DELETE ... WHERE invoice_id = :1` (`:149-150`);
  5. R via `fn_invoice_preview` (`:152`; reads of 2.7), then W `invoice_lines`
     one `INSERT` per preview line (`:153-172`, id `f_md5_uuid(invoice_id||line_no)`);
  6. W `invoices` `UPDATE subtotal, tax, total` (`:175-178`);
  7. W `credit_notes` burn-down oldest-first, `UPDATE remaining_amount =
     GREATEST(remaining - v_credit, 0)` per row (`:182-190`);
  8. W(A) `billing_audit_log` (`:192`).
- Join shapes: none beyond those in 2.4/2.7; all writes are by primary key.
  `fk_il_invoice ... ON DELETE CASCADE` (`services/legacy-billing/db/oracle/schema/01_tables.sql:132`)
  is the only cascading relation in the schema.
- **Atomic unit (the ticket's example):** rating period + rating result +
  invoice header + all invoice lines + credit-note balances must land or roll
  back together; only the audit rows are outside the boundary (autonomous).
  Re-issue of the same period is a rebuild (header updated, lines deleted and
  re-inserted) and burns down whatever credit still remains again.
- Callers: `app.py` `/api/invoices/<tenant_id>/issue`
  (`services/legacy-billing/app/app.py:66-73`). Not on the facade.

### 2.9 `invoice_lines(invoice_id)` -> `pkg_invoicing.fn_invoice_lines`

- Backend `services/legacy-billing/app/backends/oracle.py:118-119`.
- PL/SQL `services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql:102-111`:
  R `invoice_lines` by `invoice_id`, `ORDER BY line_no` (`:107`).
- W: none. Txn: read-only.
- Callers: facade `GET /invoices/<invoice_id>/lines`
  (`services/legacy-billing/app/facade.py:257-274`) after an ownership check
  `SELECT 1 FROM invoices WHERE id = :1 AND tenant_id = :2` (`:266-269`) on a
  separate connection; `app.py` `/api/invoices/<invoice_id>/lines`
  (`services/legacy-billing/app/app.py:76-79`). Facade `GET /invoices` lists
  headers with ad-hoc `invoices ⋈ rating_periods ⟕ codes('INV_STATUS')`
  (`:230-255`, SQL `:240-249`).
- Shape note: lines are only ever read by parent invoice and only ever written
  as a whole set by `sp_issue_invoice`.

### 2.10 `overdue(as_of)` -> `pkg_dunning.fn_overdue_accounts`

- Backend `services/legacy-billing/app/backends/oracle.py:122-123`.
- PL/SQL `services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql:17-31`:
  R `invoices ⟕ tenants` (`t.id (+) = i.tenant_id`, `:25-26`),
  `status_cd = 40`, `issued_at` compared as `YYYYMMDD` strings against `p_as_of`,
  `ORDER BY issued_at, id`. Tenant status decoded inline.
- W: none. Txn: read-only.
- Callers: facade `GET /admin/overdue` (`services/legacy-billing/app/facade.py:304-324`;
  admin dashboard `frontend/admin-dashboard/src/app/core/services/billing-report.service.ts:28`),
  `app.py` `/api/dunning/overdue` (`services/legacy-billing/app/app.py:81-84`).
- Estate note: no entrypoint ever sets `invoices.status_cd = 40` (or 30); the
  only transition written is `20` in `sp_issue_invoice`. Overdue state is
  produced outside the application (seed/ops), so every dunning path depends on
  externally-maintained invoice status.

### 2.11 `schedule_dunning(as_of)` -> `pkg_dunning.sp_schedule_dunning`

- Backend `services/legacy-billing/app/backends/oracle.py:126-127` (`_procedure`).
- PL/SQL `services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql:33-69`:
  cursor over `invoices WHERE status_cd = 40 ORDER BY issued_at, id` (`:40-42`;
  `p_as_of` is **not** part of the selection, only of the scheduled date);
  per invoice R `dunning_attempts` `MAX(attempt_no)` (`:43-44`); weekday roll
  via `TO_CHAR/DECODE` (`:47-50`); W `dunning_attempts` `INSERT` (`:53-58`, id
  `f_md5_uuid(invoice||attempt)`, `status_cd = 10`); `WHEN OTHERS THEN NULL`
  swallows per-row failures (`:63`); W(A) `billing_audit_log` (`:66`).
- Joins: none (nested lookup per invoice). Txn: all inserted attempts in one
  commit; a swallowed row error does not abort the batch.
- Callers: `app.py` `/api/dunning/schedule` (`services/legacy-billing/app/app.py:86-90`),
  `JOB_NIGHTLY_DUNNING` (`services/legacy-billing/db/oracle/schema/04_jobs.sql:13`).
  Facade `GET /admin/dunning` reads the result with ad-hoc
  `dunning_attempts ⟕ codes('DUN_STATUS')`, newest 200 (`services/legacy-billing/app/facade.py:326-352`).

### 2.12 `suspend_overdue(as_of)` -> `pkg_dunning.sp_suspend_overdue`

- Backend `services/legacy-billing/app/backends/oracle.py:130-131` (`_procedure`).
- PL/SQL `services/legacy-billing/db/oracle/packages/05_pkg_dunning.sql:71-99`:
  cursor `SELECT DISTINCT tenant_id FROM invoices WHERE status_cd = 40 AND
  issued_at <= as_of - 14 days` (`:74-77`); per tenant R `tenants`
  active count (`:78-79`); if active: W `tenants SET status_cd = 20` (`:81`),
  W `subscriptions SET status_cd = 20, suspended_on` for all active (status 10) rows
  (`:82-84`; fires `trg_sub_no_uncancel` and `trg_subscriptions_hist`), W
  `notifications` `INSERT ... WHERE NOT EXISTS` (kind 3 suspension, `:86-94`,
  idempotent via `uq_notifications (tenant_id, kind_cd, sent_at)`,
  `services/legacy-billing/db/oracle/schema/01_tables.sql:158-166`); W(A)
  `billing_audit_log` (`:96`).
- Joins: none. Txn: the whole sweep is one commit (`_procedure`), and in the
  scheduler it shares a transaction with `sp_schedule_dunning`.
- **Atomic unit per tenant:** tenant status + its subscriptions + the
  suspension notification + history rows.
- Callers: `app.py` `/api/dunning/suspend` (`services/legacy-billing/app/app.py:92-95`),
  `JOB_NIGHTLY_DUNNING` (`services/legacy-billing/db/oracle/schema/04_jobs.sql:13`).

## 3. Access outside the twelve entrypoints (same estate, same app)

| Path | Cite | Tables / shape | Txn |
|---|---|---|---|
| `ensure_tenant` (lazy bootstrap, called by `_ensure` on every tenant facade route and by usage ingest) | `services/legacy-billing/app/backends/oracle.py:134-169` | R `tenants` by id (`:136`); on miss W `tenants` (`:141`), R cheapest active `plans` (`:150-153`), W `subscriptions` (`:161`) | tenant + subscription in one commit (`:169`); `IntegrityError` -> rollback, treat as already present. Concurrency test `services/legacy-billing/tests/test_oracle.py:46` |
| `POST /internal/usage/events` (bridge ingest) | `services/legacy-billing/app/facade.py:356-421` | `ensure_tenant` (commits first, `:391`), R `codes('USAGE_KIND')` (`:394-397`), W `usage_events` (`:401-409`), commit (`:412`). `trg_usage_events_check` re-reads `codes` and raises `-20001/-20002` (`services/legacy-billing/db/oracle/schema/01_tables.sql:239-253`); `ORA-00001` on the deterministic event id -> `duplicate` | two transactions per call (bootstrap, then event). The only write path with real volume: census shows 814 `USAGE_EVENTS` vs 69 tenants |
| `GET /me` | `services/legacy-billing/app/facade.py:97-135` | `entitlement` + `tenants ⟕ codes` + first `customer_master` row | read-only |
| `GET /usage` | `services/legacy-billing/app/facade.py:196-227` | `usage_summary` + `usage_rating` + `usage_events ⋈ codes` newest 50 | read-only (+A from rating) |
| `GET /invoices` | `services/legacy-billing/app/facade.py:230-255` | `invoices ⋈ rating_periods ⟕ codes` by tenant | read-only |
| `GET /customer` | `services/legacy-billing/app/facade.py:277-301` | first `customer_master` row by tenant (`:286-289`), `entity_attr_value` where `entity_type='CUSTOMER'` by `entity_id` (`:293-297`) | read-only |
| `GET /admin/dunning` | `services/legacy-billing/app/facade.py:326-352` | `dunning_attempts ⟕ codes` newest 200 | read-only |
| Finance reports (`/admin/reports/*`) | `services/legacy-billing/app/reports.py:42-89` | `invoice_header ⟕ codes` by `batch_no` (`:46-50`); `invoice_header ⋈ invoice_line ⟕ codes` (`:67-73`); `customer_master` balances (`:87`) | read-only |
| `health()` | `services/legacy-billing/app/backends/oracle.py:52-53` | `SELECT 1 FROM DUAL` | none |
| `JOB_PURGE_AUDIT_LOG` | `services/legacy-billing/db/oracle/schema/04_jobs.sql:21-28` | W `billing_audit_log` DELETE older than 90 days, own COMMIT | disabled in fixture; bucket `retire` |

`customer_master`, `customer_master_hist`, `entity_attr_value`, `invoice_header`
and `invoice_line` are never written by application code; their triggers
(`services/legacy-billing/db/oracle/schema/02_horror.sql:346-374`, `:391-399`) fire
only under seed/ETL loads.

## 4. Read/write ratio per table

Static statement-site counts over the code above (application SQL, package
bodies, triggers, scheduler jobs). A "site" is one SELECT/cursor or one
INSERT/UPDATE/DELETE statement; trigger writes are counted where they fire.
This is a shape measure, not runtime volume; census row counts
(`migration/billing/census.json`, `tables[].rows`, 2026-10-02) are given as the
only live volume evidence available and are fixture-scale.

| Table | R sites | W sites | Ratio | Writers (entrypoint) | Rows | Shape hint for the model step |
|---|---|---|---|---|---|---|
| `codes` | 9 | 0 | read-only | seed only | 32 | static lookup, decoded inline or via `⟕`; candidate for app-side constants |
| `tenants` | 6 | 2 | 3:1 | `ensure_tenant` INSERT, `suspend_overdue` UPDATE status | 69 | root aggregate; status read on every request |
| `plans` | 6 | 0 | read-only | seed only | 3 | tiny reference set read by every path |
| `subscriptions` | 6 | 5 | ~1:1 | `ensure_tenant` INSERT, `change_plan` UPDATE+UPDATE+INSERT, `suspend_overdue` UPDATE | 69 | always queried by tenant for the covering/latest row; never alone |
| `subscriptions_hist` | 0 | 1 (trigger) | write-only | `trg_subscriptions_hist` on every subscription UPDATE | 0 | never read by the app |
| `usage_events` | 3 | 1 | 3:1 by sites, write-heavy by volume | `/internal/usage/events` INSERT | 814 | append-only, read as full per-tenant scan (rating) or period aggregate |
| `rating_periods` | 2 | 2 | 1:1 | `finalize_rating` upsert | 3 | 1 per tenant-period; parent of `rating_results` and `invoices` |
| `rating_results` | 1 | 2 | 1:2 | `finalize_rating` upsert | 3 | 1:1 with `rating_periods`, read only joined to it |
| `invoices` | 5 | 3 | ~2:1 | `issue_invoice` INSERT/UPDATE/UPDATE | 3 | header read by tenant, by id, and by status=40 sweep |
| `invoice_lines` | 1 | 2 | 1:2 | `issue_invoice` DELETE-all + INSERT-all | 2 | only accessed as the full set of one invoice |
| `credit_notes` | 2 | 1 | 2:1 | `issue_invoice` UPDATE remaining | 5 | per-tenant open balance, oldest-first burn-down; nothing creates them |
| `dunning_attempts` | 2 | 1 | 2:1 | `schedule_dunning` INSERT | 1 | per invoice; `MAX(attempt_no)` lookup then append |
| `notifications` | 1 | 1 | 1:1 | `suspend_overdue` INSERT (NOT EXISTS) | 1 | idempotent per (tenant, kind, day) |
| `billing_audit_log` | 0 | 2 (8 call sites + purge) | write-only | `log_msg` from `fn_list_plans`, `sp_change_plan`, `compute_rating`, `sp_finalize_rating`, `sp_issue_invoice`, `sp_schedule_dunning`, `sp_suspend_overdue`; purge job | 0 | autonomous, never read, 90-day retention; bucket says purge job `retire` |
| `customer_master` | 3 | 0 (triggers on load) | read-only | seed/ETL | 25000 | first row per tenant by `cust_seq_no`; balances by batch |
| `customer_master_hist` | 0 | 1 (trigger) | write-only | `trg_customer_master_hist` | 0 | never read |
| `entity_attr_value` | 1 | 0 | read-only | seed/ETL | 8333 | by (`entity_type`, `entity_id`) |
| `invoice_header` | 2 | 0 | read-only | seed/ETL | 18750 | report aggregates by `batch_no` |
| `invoice_line` | 1 | 0 | read-only | seed/ETL | 150000 | only joined to `invoice_header` |

Read-site cites, per table, are the ones in sections 2 and 3; the machine
readable form (same numbers) is `migration/billing/access_patterns/access_patterns.json`.

## 5. Cross-check against the census

`check.py` compares the per-package table sets stated here with
`dependencies.internal` in `migration/billing/census.json`:

| Package | Tables here | `DBA_DEPENDENCIES` | Match |
|---|---|---|---|
| `PKG_PLANS` | plans, subscriptions, tenants | same | yes |
| `PKG_RATING` | plans, rating_periods, rating_results, subscriptions, usage_events | same | yes |
| `PKG_INVOICING` | credit_notes, invoice_lines, invoices, plans, subscriptions, tenants | same | yes |
| `PKG_DUNNING` | dunning_attempts, invoices, notifications, subscriptions, tenants | same | yes |
| `PKG_OW_UTIL` | billing_audit_log (+ `codes` via `EXECUTE IMMEDIATE`, `01_pkg_util.sql:40-41`) | billing_audit_log | yes; `codes` is invisible to the dictionary because the lookup is dynamic SQL, and `f_code_desc` has no caller in the estate |

`sp_change_plan`'s dynamic INSERT and `sp_issue_invoice`'s dynamic DELETE do
not hide any table from the dictionary because the same tables are referenced
statically elsewhere in the same package body.

## 6. What this implies for the next step (inputs only)

- Atomic write sets that a single-document or transactional target must
  preserve: (a) `issue_invoice`: rating period + result + invoice header +
  lines + credit-note balances; (b) `change_plan`: close-outs + new
  subscription; (c) `suspend_overdue` per tenant: tenant + subscriptions +
  notification; (d) `ensure_tenant`: tenant + first subscription;
  (e) `finalize_rating`: period + result.
- `invoice_lines`, `rating_results` and `subscriptions_hist` are never accessed
  independently of their parent.
- `usage_events` is the only append-heavy table and is always read per tenant
  (full scan or period aggregate); `codes` and `plans` are static reference data.
- `billing_audit_log` is written from read paths and outside every business
  transaction; it is not part of any atomic unit.
- Overdue (`status_cd = 40`) is never produced by the application.
