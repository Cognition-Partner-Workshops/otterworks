# billing-db: cutover and rollback runbook

How to move the `billing` schema of `services/legacy-billing` from the database it uses
today to the managed RDS PostgreSQL 16 instance defined in this directory, how to go back,
and how to retire the source afterwards (plan step s4.5).

**Nothing in this file has been executed.** This wave is plan only: no RDS instance or
cluster exists, no `terraform apply` has been run, no data has moved, and no SQL below has
been run against any database. In this wave billing uses only the tenant's database on the
shared instance. The runbook is written for the next wave, which also delivers the
prerequisites in section 1.

References (paths are relative to the repository root):

- Terraform: `infrastructure/terraform/billing-db/` at commit `0cb49f6e4`
  (`main.tf`, `variables.tf`, `outputs.tf`, `bootstrap/create-database.sql`, `README.md`).
- Offline CI plan output (mock credentials, `Plan: 7 to add, 0 to change, 0 to destroy`):
  <https://github.com/Cognition-Partner-Workshops/otterworks/pull/2215#issuecomment-6374364731>.
- Inventory: `services/legacy-billing/db/MANAGED_POSTGRES.md` (written "the inventory" below):
  roles and grants (section 2), UTC (section 3), ISO `DateStyle` (section 4), TLS
  `verify-full` (section 7), 15 vs 16 (section 8).
- Data-move decision (ticket): `pg_dump`/`pg_restore` inside a write freeze on the source.

## 0. Roles in this runbook

| Who | Does |
| --- | --- |
| Change owner | Holds the go/no-go decision at every gate and the final sign-off |
| Operator | Runs the commands, fills in the evidence table (section 11) |
| Reviewer | Checks the evidence table before the switch (step 7) and before decommission (step 10) |

The operator works from a host **inside the `otterworks-dev` VPC**: the target security
group admits 5432/tcp from the VPC CIDR only (`main.tf`, `aws_vpc_security_group_ingress_rule.postgres`).
A one-off pod with the `postgres:16` image is fine. Do not create a `LoadBalancer` Service
or any other AWS resource from Kubernetes to reach either database.

Client tools: `psql`, `pg_dump`, `pg_restore` of major **16** (the target major; `pg_dump`
must be at least the source's major). TLS for every connection, source and target:
`sslmode=verify-full sslrootcert=global-bundle.pem` (AWS RDS global CA bundle; the target
chains to `rds-ca-rsa2048-g1`, Terraform output `ca_cert_identifier`).

Connection strings used below (fill in before the window; never paste passwords into the
evidence):

```bash
# Source: the database legacy-billing uses today.
export SRC="host=<source host> port=5432 dbname=<source db> user=<source login> sslmode=verify-full sslrootcert=global-bundle.pem"
# Target, as the migration login that may SET ROLE billing_owner (section 1).
export TGT_OWNER="host=<terraform output address> port=5432 dbname=billing user=<migration login> sslmode=verify-full sslrootcert=global-bundle.pem"
# Target, as the application role.
export TGT_APP="host=<terraform output address> port=5432 dbname=billing user=billing_app sslmode=verify-full sslrootcert=global-bundle.pem"
```

Passwords come from `PGPASSWORD` set from the secret store for the duration of one command,
or from a `~/.pgpass` with mode `0600` on the operator host that is deleted after the window.

## 1. Prerequisites delivered by the next wave

These are **not** in this wave. Each one must be merged (reviewed, never merged by a
session) before the change window is booked.

| # | Prerequisite | Delivered by | What "done" means |
| --- | --- | --- | --- |
| P1 | Ordered migrations for the managed database | procedure port (deferred) | A load step that applies `services/legacy-billing/db/schema.sql`, `procs/plans.sql`, `procs/rating.sql`, `procs/invoicing.sql`, `procs/dunning.sql` in that order, **without `seed.sql`**, as `billing_owner` (inventory section 2, "Load step"). Tables before procedures, because `LANGUAGE sql` bodies are validated at `CREATE` time. |
| P2 | Role and grant script | procedure port (deferred) | Run as the RDS master user: `billing_owner` `NOLOGIN` owns database, schema, 11 tables and the 12 entrypoints; `billing_app` `LOGIN` gets `CONNECT`, `USAGE ON SCHEMA billing`, `SELECT, INSERT, UPDATE, DELETE` on all tables, `EXECUTE` on the 12 entrypoints with `EXECUTE` revoked from `PUBLIC`, and `ALTER DEFAULT PRIVILEGES FOR ROLE billing_owner IN SCHEMA billing` for later objects (inventory section 2 table and row 12). Migrations log in as a migration login and `SET ROLE billing_owner`. On PostgreSQL 16 the creator of a role does not get `SET` on it by default (`createrole_self_grant` is empty), so the script must `GRANT billing_owner TO <migration login> WITH SET TRUE, INHERIT FALSE` explicitly. The master user is never the owner and never the app. |
| P3 | `billing_app` credential in a secret | connection changes (deferred) | A secret holding the `billing_app` password (not the RDS-managed master secret, Terraform output `master_user_secret_arn`, which stays for administration only), wired into the legacy-billing deployment as `DB_PASSWORD`. |
| P4 | TLS knobs in `db_connect()` | connection changes (deferred) | Optional `DB_SSLMODE` / `DB_SSLROOTCERT` in `services/legacy-billing/app/app.py:12-19`, defaulting to today's behaviour so the Compose stack (TLS off) keeps working; the RDS bundle mounted or baked into the image (`python:3.12-slim` does not trust the RDS CAs). Until then libpq's `PGSSLMODE`/`PGSSLROOTCERT` work with the unmodified code (inventory section 7, rows 10-11). |
| P5 | Parity CI runs again | procedure port (deferred) | `.github/workflows/procs-parity.yml` pinned to Python 3.12, because `psycopg-binary` 3.2.9 has no `cp314` wheel and the job currently stops before replay. |
| P6 | A real, reviewed `terraform plan` | next wave | See step 2.1. |

## 2. Preconditions (all must hold before the window opens)

### 2.1 Reviewed Terraform plan, then apply

1. The offline CI plan in the PR comment above is only a shape check (mock credentials,
   literal network ids from `ci/offline.tfvars`). Produce a real plan against
   `otterworks-dev` with the real `run_token` and `expires`, the S3 backend, and the engine
   version pinned to `16.15` (`variables.tf`, `engine_version`).
2. The reviewer confirms in the plan: `7 to add, 0 to change, 0 to destroy`;
   `storage_encrypted = true`; `deletion_protection = true`; `publicly_accessible = false`;
   `manage_master_user_password = true`; `backup_retention_period >= 7`;
   `skip_final_snapshot = false`; parameter group `postgres16` with `rds.force_ssl=1`,
   `ssl_min_protocol_version=TLSv1.2`, `timezone=UTC`, `datestyle=ISO, MDY`
   (`main.tf`, `local.db_parameters`); ingress only 5432/tcp from the VPC CIDR.
   `ci/check-plan.py` passes on the plan JSON.
3. `expires` is later than the end of the sign-off period (step 9) plus the decommission
   (step 10): every resource carries `Expires` through `default_tags`, and a production
   billing database must not carry a date before it is meant to go away.
4. The change owner approves the plan; the apply is a separate reviewed change. No session
   applies it on its own.
5. After apply: run `bootstrap/create-database.sql` as the master user (README, "Database
   bootstrap"), then P2 (roles), then P1 (migrations, step 4).

### 2.2 Source facts, recorded in the evidence table

```sql
-- On the source. Read-only.
SELECT version();
SHOW server_version;          -- the shared instance is 15.x (infrastructure/terraform/modules/database/main.tf: engine_version "15.7"); target 16 is newer, so a 16 dump client is fine
SHOW TimeZone; SHOW DateStyle; -- expect UTC / ISO, MDY (inventory rows 1, 13)
SELECT current_database(), datcollate, datctype FROM pg_database WHERE datname = current_database();
SELECT n.nspname, c.relname, pg_get_userbyid(c.relowner) AS owner
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'billing' AND c.relkind IN ('r', 'p') ORDER BY c.relname;   -- expect 11 tables
SELECT p.proname, l.lanname, p.prokind, p.prosecdef, pg_get_userbyid(p.proowner)
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace JOIN pg_language l ON l.oid = p.prolang
 WHERE n.nspname = 'billing' ORDER BY p.proname;                                -- expect 12: 7 plpgsql + 5 sql, prosecdef f
SELECT pg_size_pretty(sum(pg_total_relation_size(c.oid)))
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'billing';
-- Does the source database hold anything besides billing? (decides the freeze guard in step 3)
SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\_%' AND nspname <> 'information_schema' ORDER BY 1;
-- Which roles can write billing tables? (needed for guard B and for rollback)
SELECT grantee, table_name, string_agg(privilege_type, ',' ORDER BY privilege_type)
  FROM information_schema.role_table_grants
 WHERE table_schema = 'billing' AND privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE')
 GROUP BY 1, 2 ORDER BY 1, 2;
```

Also record which login legacy-billing uses (`DB_USER` of its deployment) and every other
writer of `billing.*` (jobs, scripts, other services). Only legacy-billing is known in the
repository (`services/legacy-billing/app/app.py`); confirm there is no other.

**Schema drift check.** The target is built from the repository SQL (P1), so the source must
match it. Compare `pg_dump --schema-only --schema=billing --no-owner --no-privileges` of the
source with the same dump of the target after step 4 (both with pg_dump 16). Any
difference other than ownership/privileges stops the change.

### 2.3 Change window

- Book a window long enough for steps 3 to 7. Billing writes are unavailable from step 3
  until step 7 (reads keep working on the source until step 7). Measure the real
  dump/restore time in the rehearsal (2.5) and book at least twice that plus 60 minutes for
  the checks.
- Announce the freeze to everyone who calls legacy-billing; nobody runs invoicing,
  rating finalisation or dunning inside the window.
- The change owner, operator and reviewer are reachable for the whole window and for the
  first hour after the switch.

### 2.4 Backups

- **Source:** a full logical backup of the billing schema, taken inside the freeze (step 3.4).
  Before the window, also confirm the source's own recovery point: on the shared RDS
  instance, automated backups with a known point-in-time window. A manual snapshot of the
  shared instance is optional and is a decision for the instance owner, because it covers
  every tenant on it. **Tenant teardown and the reaper drop the whole tenant database**
  (`scripts/lib/tenant-common.sh`, `DROP DATABASE ... WITH (FORCE)`), so the tenant must not
  be reaped or torn down between the window and decommission, and the tenant database is
  never treated as a backup.
- **Target:** automated backups on (7 days, `backup_retention_period`), `deletion_protection`
  on, final snapshot on destroy (`main.tf`). Take a manual snapshot of the target after
  step 4 (empty schema) so a failed restore can start again from a known state.
- Store the dump files on encrypted storage with access limited to the operator and the
  change owner. They contain all billing data.

### 2.5 Rehearsal

Run steps 3 to 6 once end to end against a disposable copy (a throwaway `postgres:16`
database created with `bootstrap/create-database.sql`) before the real window, and record
the timings. Never point `procs/harness/record.py` at the source or the target: its
`reset_database()` runs `DROP SCHEMA IF EXISTS billing CASCADE` (inventory section 2,
"Harness"). Recordings stay on the disposable Compose stack.

### 2.6 Go / no-go for the window

Proceed only when P1 to P6 are merged, 2.1 to 2.5 are done, the evidence table has the source
facts, the target has passed step 4's checks, and the change owner says go.

## 3. Freeze the source

### 3.1 Stop every writer

Scale legacy-billing to zero replicas (or stop its container) and disable every other writer
found in 2.2. Confirm no billing session is left:

```sql
SELECT pid, usename, application_name, client_addr, state, xact_start
  FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();
```

### 3.2 Server-side guard

Stopping the app is not enough on its own; add a guard on the server. Which one depends on
2.2:

- **Guard A, the source database holds only billing.**
  `ALTER DATABASE <source db> SET default_transaction_read_only = on;` then terminate the
  remaining sessions of the billing login with `pg_terminate_backend(pid)`. New sessions
  start read-only.
- **Guard B, the source database is shared (the tenant database on the shared instance).**
  Do not make the database read-only; that would stop other services. Instead revoke the
  write privileges on the billing schema only, for every non-superuser role found in 2.2
  (including the owner, which can revoke its own privileges and grant them back):

  ```sql
  REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA billing FROM <role>;
  ```

  Save the 2.2 grant listing in the evidence; rollback (step 8) grants exactly those back.

If the billing writer is a true superuser (as in the Compose fixture, where `billing` is the
cluster superuser, inventory section 1), neither guard binds it: stopping the writer (3.1)
and the content check (3.3, 6.3) are then the only protection, and the change owner has to
accept that explicitly.

### 3.3 Freeze snapshot `S0`

Row count and content hash of every `billing` table. Run the same script on every side and
at every checkpoint (`S0`, `T0`, `S1`, `T_rb`), and diff the outputs:

```bash
cat > billing-snapshot.sql <<'SQL'
SET TimeZone = 'UTC';
SET DateStyle = 'ISO, MDY';
SELECT format(
  'SELECT %L AS table_name, count(*) AS row_count, '
  'md5(coalesce(string_agg(t::text, E''\n'' ORDER BY t::text COLLATE "C"), '''')) AS content_md5 '
  'FROM billing.%I t', c.relname, c.relname)
  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'billing' AND c.relkind IN ('r', 'p')
 ORDER BY c.relname
\gexec
SQL
psql "$SRC" -X -At -F ',' -v ON_ERROR_STOP=1 -f billing-snapshot.sql > S0.csv
```

`S0.csv` must list the 11 tables: `credit_notes`, `dunning_attempts`, `invoice_lines`,
`invoices`, `notifications`, `plans`, `rating_periods`, `rating_results`, `subscriptions`,
`tenants`, `usage_events` (`services/legacy-billing/db/schema.sql`).

### 3.4 Dump

Two custom-format dumps of the billing schema, both inside the freeze:

```bash
# Full backup of the schema (DDL + data). Kept as the source backup and for the disposable copy in 6.2.
pg_dump "$SRC" --format=custom --schema=billing --no-owner --no-privileges --file=billing-full.dump
# Data only. This is what moves to the target.
pg_dump "$SRC" --format=custom --schema=billing --data-only --file=billing-data.dump
pg_restore --list billing-data.dump > billing-data.toc   # 11 TABLE DATA entries, nothing else expected
sha256sum billing-full.dump billing-data.dump           # into the evidence table
```

Why data only: the target's schema, procedures, owner and grants come from the reviewed
migrations (P1, P2), and the inventory advises against restoring a container dump's DDL on
the managed instance (section 8). The data dump carries no DDL, so it cannot change
ownership or grants. `pg_dump` writes `timestamptz` with an explicit offset and in ISO
format, so values are exact whatever the session time zone. The schema has no sequences,
identity columns or triggers (all keys are `uuid`), and its foreign keys have no cycles, so
a data-only restore loads the tables in dependency order with no extra steps.

## 4. Apply the migrations on the target, under the owner role

Done before the window (it does not need the freeze) and re-checked inside it.

1. P2 role script as the master user, P1 migrations as the migration login with
   `SET ROLE billing_owner`. No `seed.sql`.
2. Checks, all recorded in the evidence:

```sql
-- As TGT_OWNER
SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname = 'billing';       -- billing_owner
SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'billing' AND c.relkind = 'r' AND pg_get_userbyid(c.relowner) = 'billing_owner';  -- 11
SELECT l.lanname, count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
  JOIN pg_language l ON l.oid = p.prolang WHERE n.nspname = 'billing' GROUP BY 1;    -- plpgsql 7, sql 5
SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE n.nspname = 'billing' AND (p.prosecdef OR p.proconfig IS NOT NULL);           -- 0
SELECT datcollate FROM pg_database WHERE datname = 'billing';                         -- en_US.UTF-8
```

```bash
# As billing_app: the session settings billing results depend on (inventory rows 6, 7, 13).
psql "$TGT_APP" -X -At -c "SHOW TimeZone" -c "SHOW DateStyle" -c "SELECT ssl, version FROM pg_stat_ssl WHERE pid = pg_backend_pid()"
# expect: UTC / ISO, MDY / t|TLSv1.2 or TLSv1.3
psql "$TGT_OWNER" -X -At -F ',' -v ON_ERROR_STOP=1 -f billing-snapshot.sql > T_empty.csv   # every row_count 0
```

3. Schema drift check from 2.2 against the source.

## 5. Move the data

```bash
pg_restore --dbname="$TGT_OWNER" --role=billing_owner --data-only --no-owner \
  --single-transaction --exit-on-error billing-data.dump
psql "$TGT_OWNER" -X -c "ANALYZE billing.tenants, billing.plans, billing.subscriptions, billing.usage_events, billing.rating_periods, billing.rating_results, billing.invoices, billing.invoice_lines, billing.credit_notes, billing.dunning_attempts, billing.notifications"
```

`--role=billing_owner` makes `pg_restore` `SET ROLE` to the owner after connecting, so the
rows are written by the owner role. `--single-transaction` means a failure leaves the
target empty; fix the cause and re-run from the post-step-4 state. Do not use `--jobs` with
`--single-transaction` (they cannot be combined), and do not restore `billing-full.dump`
here.

## 6. Verify

### 6.1 Row counts (and content) of every table

```bash
psql "$TGT_OWNER" -X -At -F ',' -v ON_ERROR_STOP=1 -f billing-snapshot.sql > T0.csv
diff -u S0.csv T0.csv && echo "IDENTICAL"
```

Gate: 11 lines on both sides, identical `row_count` for every table. The `content_md5`
column is a stricter extra check (same rows, same values); a difference there with equal
counts is a failure too.

### 6.2 Procedure by procedure

Call each of the 12 entrypoints with the same inputs on source and target and compare the
results. The input sets are the 24 recorded scenarios in `procs/scenarios/`, which cover
every entrypoint; each file has the `inputs`, and for procedures the `capture_query` and
`probes` that read the state the procedure leaves behind.

| Entrypoint | Kind | Writes | Scenarios |
| --- | --- | --- | --- |
| `billing.fn_list_plans()` | function | no | `plans/001` |
| `billing.fn_entitlement(tenant, on)` | function | no | `plans/002`, `plans/003` |
| `billing.sp_change_plan(tenant, plan, effective_on)` | procedure | `subscriptions` | `plans/004`, `plans/005` |
| `billing.fn_usage_rating(tenant, start, end)` | function | no | `rating/001`-`006` |
| `billing.fn_usage_summary(tenant, start, end)` | function | no | `rating/007` |
| `billing.sp_finalize_rating(tenant, start, end)` | procedure | `rating_periods`, `rating_results` | `rating/008` |
| `billing.fn_invoice_preview(tenant, start, end)` | function | no | `invoicing/001`, `invoicing/002` |
| `billing.fn_invoice_lines(invoice)` | function | no | `invoicing/006` |
| `billing.sp_issue_invoice(tenant, start, end)` | procedure | `invoices`, `invoice_lines`, `credit_notes` | `invoicing/003`-`005` |
| `billing.fn_overdue_accounts(as_of)` | function | no | `dunning/001` |
| `billing.sp_schedule_dunning(as_of)` | procedure | `dunning_attempts` | `dunning/002`, `dunning/003` |
| `billing.sp_suspend_overdue(as_of)` | procedure | `tenants`, `subscriptions`, `notifications` | `dunning/004`, `dunning/005` |

The scenario inputs use the seed's tenant, plan and invoice ids
(`services/legacy-billing/db/seed.sql`). If the moved data is not the seed, the reviewer
picks at least one real input per entrypoint (a tenant with usage, an issued invoice, an
`as_of` with overdue invoices) and writes the inputs into the evidence **before** running
anything. Same inputs on both sides, always.

Every session sets `SET TimeZone = 'UTC'; SET DateStyle = 'ISO, MDY';` first and runs with
`psql -X -At -v ON_ERROR_STOP=1`, writing one output file per scenario and side.

**Read-only functions (7): directly on source and target.**

```sql
SELECT r::text FROM billing.fn_invoice_preview(
  '00000000-0000-0000-0000-000000000006'::uuid, '2026-02-01'::date, '2026-02-28'::date) AS r;
```

Compare the outputs in the order returned. A difference only in row order counts as an
order-only difference, and only for a function without a top-level `ORDER BY`; compare
those sorted and record the reason. Everything else is a failure.

**Mutating procedures (5): target inside a rolled-back transaction, as `billing_app`.**

```sql
-- psql "$TGT_APP"
BEGIN;
CALL billing.sp_issue_invoice('00000000-0000-0000-0000-000000000009'::uuid, '2026-02-01'::date, '2026-02-28'::date);
-- the scenario's capture_query, then each probe query, e.g. procs/scenarios/invoicing/003.yaml:
SELECT id::text, issued_on::text, remaining_amount::text FROM billing.credit_notes
 WHERE tenant_id = '00000000-0000-0000-0000-000000000009' ORDER BY issued_on, id;
ROLLBACK;
```

Running these as `billing_app` also proves the P2 grants (a missing grant shows up as
`permission denied`, inventory row 12). None of the procedures commits or rolls back on
its own (inventory section 7), so `ROLLBACK` discards everything. One scenario per
transaction, so each one starts from the restored state.

**Mutating procedures: the source side.**

- Guard A: the same transaction on the source, opened with `BEGIN READ WRITE;` (allowed
  under `default_transaction_read_only`) and ended with `ROLLBACK;`. Writers are stopped,
  so nothing else runs meanwhile.
- Guard B (or when the change owner does not want any write attempt on the source): a
  disposable copy. Create a throwaway `postgres:16` database with
  `bootstrap/create-database.sql`, restore `billing-full.dump` into it, and run the same
  transactions there. It holds the frozen source data, byte for byte.

Gate: for all 24 scenarios (or the reviewer's inputs), the function output and the
capture/probe output are identical between source and target. Each one is a row in the
evidence table; a failed row is reported as failed.

### 6.3 Freeze held

```bash
psql "$SRC" -X -At -F ',' -v ON_ERROR_STOP=1 -f billing-snapshot.sql > S1.csv
diff -u S0.csv S1.csv && echo "SOURCE UNCHANGED"
```

Gate: identical. This proves no write reached the source during the window, including the
rolled-back checks. Re-run on the target too; it must still equal `T0.csv`.

### 6.4 Go / no-go for the switch

The reviewer checks the evidence table (6.1 to 6.3 all pass) and the change owner decides.
On no-go, stop here and follow step 8 "before the switch".

## 7. Switch `DB_HOST` and the secret

In the legacy-billing deployment (environment read by `db_connect()`,
`services/legacy-billing/app/app.py:12-19`):

| Variable | Before | After |
| --- | --- | --- |
| `DB_HOST` | source host | Terraform output `address` |
| `DB_PORT` | source port | Terraform output `port` (5432) |
| `DB_NAME` | source database | Terraform output `database_name` (`billing`) |
| `DB_USER` | source login | `billing_app` |
| `DB_PASSWORD` | source secret | the `billing_app` secret from P3 |
| `DB_SSLMODE` (or `PGSSLMODE`) | unset (`prefer`) | `verify-full` (P4) |
| `DB_SSLROOTCERT` (or `PGSSLROOTCERT`) | unset | path of the RDS global bundle in the container (P4) |

Never put the master secret (`master_user_secret_arn`) into the application. Keep the
previous values written down (in the evidence, without the password) for step 8.

Then:

1. Apply the change and restart legacy-billing (a config change does not restart pods by
   itself), scaled back to its normal replica count.
2. Smoke test through the app: `GET /health` returns `{"status": "UP"}`; `GET /plans`
   renders the same plans as `fn_list_plans` on the source; one read call per module
   (`/plans/<tenant>/entitlement`, `/api/rating/preview`, `/api/invoices/<tenant>/preview`,
   `/api/dunning/overdue`) returns the values recorded in 6.2 (routes:
   `services/legacy-billing/README.md`).
3. On the target, as the master user (it can read every session's TLS status), confirm the
   app's sessions are `billing_app` over TLS:

```sql
SELECT a.usename, s.ssl, s.version FROM pg_stat_activity a JOIN pg_stat_ssl s USING (pid)
 WHERE a.datname = 'billing' AND a.usename = 'billing_app';
```

4. Re-enable the other writers from 2.2 against the new connection settings.
5. The **source stays frozen** (guard A or B in place) until sign-off (step 9).

## 8. Rollback

### Before the switch (any gate in 4 to 6 failed)

Nothing has moved yet for the application, so there is little to undo:

1. Lift the source guard: guard A `ALTER DATABASE <source db> RESET default_transaction_read_only;`;
   guard B `GRANT` exactly the privileges saved in 2.2 back to each role.
2. Restart legacy-billing and the other writers on the unchanged source settings; smoke
   test as in 7.2.
3. Empty the target for the next attempt (restore the post-step-4 snapshot, or
   `TRUNCATE` the 11 tables as `billing_owner`). Record what failed.

### After the switch (smoke test failed, wrong results, error rate)

The change owner decides; the operator then:

1. Stops legacy-billing and the other writers again.
2. Takes `T_rb`: `billing-snapshot.sql` on the target, and
   `pg_dump --format=custom --schema=billing --data-only` of the target as evidence.
   `diff T0.csv T_rb.csv` shows whether the target accepted writes after the switch.
3. If it did, those rows exist **only on the target**. Rolling back discards them unless
   they are re-applied on the source by repeating the same requests (procedure ids are
   deterministic `md5` values, inventory section 4, so re-running the same calls produces
   the same keys). The change owner decides between re-applying and accepting the loss,
   and that decision goes into the evidence before step 4 of this list.
4. Points the deployment back at the source: restore the "Before" column of the step-7
   table and restart.
5. Lifts the source guard as above, re-enables the writers, smoke tests against the source.
6. Leaves the target running and untouched for analysis. It is not deleted as part of a
   rollback (`deletion_protection` stays on).

Rollback stays possible without data loss only while the source is frozen and the target has
taken no writes, which is why the source stays read-only until sign-off.

## 9. Sign-off

After an agreed period on the target (at least one full billing cycle that runs rating
finalisation, invoicing and dunning on the target), the change owner signs off when:

- no rollback was needed and the app's errors are not above their pre-cutover level;
- the evidence table is complete and reviewed;
- `S1.csv` still equals the source today (the source never moved).

Sign-off ends the rollback option. Record the date.

## 10. Decommission the source

Only after sign-off, and as a separate reviewed change:

1. Final source backup: `pg_dump --format=custom --schema=billing` once more; keep it with
   `billing-full.dump` under the agreed retention.
2. Remove the source connection settings and the source secret from the legacy-billing
   deployment and from every other writer.
3. Remove the billing data from the source:
   - shared tenant database (guard B): as the billing schema's owner,
     `DROP SCHEMA billing CASCADE;` in that database only. Never `DROP DATABASE`: the tenant
     database holds the other services' data;
   - dedicated billing database (guard A): drop that database after confirming it holds
     nothing but `billing` (the 2.2 schema listing).
4. Revoke and drop the source login if it existed only for billing.
5. Delete the dump files from the operator host once they are in the retention store.
6. Note on the evidence table that the source is gone, and when.

The target keeps `deletion_protection`, its automated backups and the final-snapshot
setting from `main.tf`.

## 11. Evidence table

Filled in during the rehearsal and the window. One row per check; a failed row is reported
as failed, never rounded up.

| # | Check | Source value | Target value | Result |
| --- | --- | --- | --- | --- |
| E1 | Reviewed `terraform plan`, approver, date (2.1) | n/a | | |
| E2 | Source version, `TimeZone`, `DateStyle`, collation (2.2) | | | |
| E3 | Source holds only billing? Guard A or B (2.2, 3.2) | | n/a | |
| E4 | Write grants on `billing.*` before the freeze (2.2) | | n/a | |
| E5 | Schema drift: `--schema-only` diff, owner/privileges ignored (2.2, 4) | | | |
| E6 | Target catalog: owner, 11 tables, 7 plpgsql + 5 sql, no `SECURITY DEFINER` (4) | n/a | | |
| E7 | `billing_app` session: `UTC`, `ISO, MDY`, TLS (4) | n/a | | |
| E8 | Freeze start time, writers stopped, guard applied (3) | | n/a | |
| E9 | Dump sha256 and TOC (3.4) | | n/a | |
| E10 | Restore exit status and duration (5) | n/a | | |
| E11 | Row counts and content hashes, 11 tables (6.1) | `S0.csv` | `T0.csv` | |
| E12 | 24 scenario comparisons, one sub-row each (6.2) | | | |
| E13 | Source unchanged `S0` = `S1` (6.3) | | | |
| E14 | Switch time, smoke test, `pg_stat_ssl` (7) | n/a | | |
| E15 | Rollback (if any): `T_rb` diff, decision on target-only rows (8) | | | |
| E16 | Sign-off date and owner (9) | | | |
| E17 | Source decommissioned, date (10) | | n/a | |
