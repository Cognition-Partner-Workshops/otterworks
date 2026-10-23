# legacy-billing database: cutover and rollback runbook

This runbook covers moving the `billing` schema from the database legacy-billing
uses today to the dedicated RDS for PostgreSQL 16 instance in
`infrastructure/terraform/legacy-billing-db/`. **It is a plan. Nobody has run
it.** It was written without connecting to any live database or AWS account.
Each step that is hard to undo has a named approver (see
[Approvals](#approvals)). An automated session must not carry out any step
here. The only commands that have been executed are the fingerprint query, the
freeze, and the data-only dump and single-transaction restore as
`billing_owner`. They were run against a throwaway local `postgres:16`
container loaded with `seed.sql`, restoring into a schema built by
`roles.sql` and `migrate.sh`, and the fingerprints matched on all 11 tables.

Related documents: `MANAGED_POSTGRES.md` (inventory and findings),
`../README.md` ("Connection settings", "Applying to managed PostgreSQL"),
`infrastructure/terraform/legacy-billing-db/README.md` and `procs/README.md`
("Migrated-schema parity").

## Approach

The recommended approach is **`pg_dump`/`pg_restore` of the `billing` schema
data during a short write freeze.** The schema is 11 tables with no sequences,
identity columns, triggers or large objects, and every key is supplied by the
caller. A data-only dump into a schema that the migration runner built is
small, needs no superuser on the target, and leaves the source untouched,
which keeps rollback simple. **AWS DMS** (full load plus CDC) is the
alternative if billing cannot accept a freeze. See
[Zero-downtime alternative](#zero-downtime-alternative-aws-dms).

| Term | Meaning |
|---|---|
| source | The database the app's current `DB_HOST`/`DB_NAME` point at. Today that is the `postgres:16` from `docker-compose.procs.yml`, where the app connects as the bootstrap superuser `billing`. |
| target | The RDS instance `<run_token>-legacy-billing`, database `billing` (Terraform `db_name`). |
| `billing_admin` | The RDS master user (Terraform `master_username`). Its password is the RDS-managed secret `master_user_secret_arn`. Use it only for `roles.sql`, for creating or dropping the scratch database, and for `ALTER ROLE ... PASSWORD`. |
| `billing_owner` / `billing_app` | The owner and runtime roles from `db/bootstrap/roles.sql`. `migrate.sh` and `pg_restore` run as `billing_owner`. The app runs as `billing_app`. |

## Prerequisites (T-1 week)

1. **Rehearse.** Run the whole runbook once against a non-production copy:
   the same Terraform stack with a different `run_token`, and a source restored
   from a recent backup. Record how long the dump, restore and verification
   take. Those timings set the length of the freeze window. Measure the source
   size with `SELECT pg_size_pretty(sum(pg_total_relation_size(c.oid))) FROM
   pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname =
   'billing'`.
2. **Local proofs on the release commit** (no cloud access needed):
   - `make billing-migrate-verify` ends in `g-migrate-clean: PASS`.
   - `make billing-tls-verify NS=<ns>` ends in `g-billing-tls: PASS`.
   - `make procs-up NS=<ns>` + `make procs-schema-parity-original NS=<ns>`,
     then `make procs-up-migrated NS=<ns>` + `make procs-schema-parity NS=<ns>
     BASELINE=procs/reports/schema-parity-original.json` passes 24/24 with
     matching seed-quirk outcomes. Keep
     `procs/reports/schema-parity-original.json`, because step 4 uses it as the
     baseline.
3. **Operator host.** You need a host that can reach the target. The `<name>-db`
   security group admits 5432 only from `<name>-client`
   (`client_security_group_id`), so run from a pod or job that has the client
   SG attached through a `SecurityGroupPolicy` together with the cluster SG
   (see the stack README). The host needs PostgreSQL 16 client tools (`psql`,
   `pg_dump`, `pg_restore`, the same version as or newer than both servers), a
   checkout of the release commit, and the RDS CA bundle:
   `curl -o rds-global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem`
   (the same file the `Dockerfile` bakes into the image).
4. **App password secret.** Create a Secrets Manager secret for `billing_app`
   (JSON `{"password": "..."}`). Terraform does not create it, and the RDS
   master secret must not be reused for this. Grant the app's runtime identity
   `secretsmanager:GetSecretValue` on the secret, plus `kms:Decrypt` if the
   secret uses a customer-managed key. `billing_owner`'s password stays with the
   operator (for example, a second secret that only the migration job can read).
5. **Write down the current `DB_*` values** for the running app. The rollback
   step uses them.
6. **Fingerprint query.** Save this as `billing-fingerprint.sql`. It prints a
   row count and a content hash for each `billing` table. Always run it with
   the `PGOPTIONS` shown in step 5.2, which pin the text format so the same
   rows produce the same hash on source and target.
   ```sql
   SELECT format('%s rows=%s md5=%s', c.relname, x.n, x.h)
   FROM pg_class c
   JOIN pg_namespace ns ON ns.oid = c.relnamespace
   CROSS JOIN LATERAL (
     SELECT (xpath('/row/n/text()', q))[1]::text AS n,
            (xpath('/row/h/text()', q))[1]::text AS h
     FROM query_to_xml(format(
       'SELECT count(*) AS n, md5(coalesce(string_agg(t::text, %L ORDER BY t::text), %L)) AS h FROM billing.%I t',
       '|', '', c.relname), false, true, '') AS q
   ) x
   WHERE ns.nspname = 'billing' AND c.relkind = 'r'
   ORDER BY c.relname;
   ```

## Step 1: Provision the target (T-3 days)

Approval: **A1**.

```bash
cd infrastructure/terraform/legacy-billing-db
terraform init -backend-config="key=otterworks/legacy-billing-db/<run_token>/terraform.tfstate"
terraform plan -var run_token=<run_token> -var expires=<date> -out=tfplan   # review: 1 aws_db_instance, no destroys
terraform apply tfplan
terraform output   # address, port, db_name, master_username, master_user_secret_arn, client_security_group_id
```

For production, set `-var multi_az=true` and choose `backup_retention_days`.
The defaults are `false` and `7`. `deletion_protection` defaults to `true`;
leave it on.

Check the instance from the operator host. Export the master password from
the secret into `PGPASSWORD` for this shell only, and don't write it to a
file:

```bash
export PGHOST=<address> PGPORT=5432 PGDATABASE=billing \
       PGSSLMODE=verify-full PGSSLROOTCERT=$PWD/rds-global-bundle.pem
PGUSER=billing_admin psql -X -tAc "SELECT current_setting('server_version'), current_setting('rds.force_ssl'), current_setting('TimeZone'), (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid())"
#   expect: 16.x|on|UTC|t
PGSSLMODE=disable PGUSER=billing_admin psql -X -c 'SELECT 1'
#   expect: rejected (rds.force_ssl=1, no pg_hba entry for an unencrypted connection)
```

## Step 2: Roles and migrations on the target (T-3 days)

Approval: none (empty database, repeatable).

```bash
PGUSER=billing_admin psql -X -v ON_ERROR_STOP=1 \
  -v owner_role=billing_owner -v app_role=billing_app \
  -f services/legacy-billing/db/bootstrap/roles.sql
PGUSER=billing_admin psql -X        # \password billing_owner, then \password billing_app (the value stored in the app secret)

PGUSER=billing_owner BILLING_APP_ROLE=billing_app services/legacy-billing/db/migrate.sh
#   expect: apply 0001_billing_schema.sql ... apply 0006_app_grants.sql; a rerun prints only "skip"
```

**Do not load `seed.sql` into the target.** It is test data, and the restore in
step 5 needs empty tables. Check that all 11 tables are empty:

```bash
PGUSER=billing_owner psql -X -tA -f billing-fingerprint.sql
#   expect: 11 lines, each rows=0
```

## Step 3: Point a staging app at the target (T-3 days)

Approval: none.

Run one throwaway app instance, not the production one, with the target
settings from [step 6](#step-6-switch-db_-settings), and check that it reaches
the database as the app:

```bash
python -c "from app import db_connect; c = db_connect(); print(c.execute('SELECT current_user, (SELECT ssl FROM pg_stat_ssl WHERE pid = pg_backend_pid())').fetchone())"
#   expect: ('billing_app', True)
curl -fsS http://<staging-app>:8096/health      # {"status":"UP"}
curl -fsS http://<staging-app>:8096/plans       # []  (empty target)
```

This also covers the secret path (`DB_PASSWORD_SECRET_ARN`), IAM, the pod
security group and the baked CA bundle (`DB_SSLROOTCERT` unset, so
`verify-full` selects `/etc/ssl/certs/rds-global-bundle.pem`).

## Step 4: Parity replay on the RDS instance (T-3 days)

Approval: none (scratch database only).

The replay rebuilds its database before every scenario (`DROP SCHEMA billing
CASCADE`, then `migrate.sh` and `seed.sql`). **Never point it at the target
database `billing`.** Run it in a scratch database on the same instance with
its own role pair. Role names are cluster-wide, so the pair needs its own
names:

```bash
PGUSER=billing_admin psql -X -d billing -c 'CREATE DATABASE billing_parity'
PGUSER=billing_admin psql -X -d billing_parity -v ON_ERROR_STOP=1 \
  -v owner_role=billing_owner_parity -v app_role=billing_app_parity \
  -f services/legacy-billing/db/bootstrap/roles.sql
PGUSER=billing_admin psql -X -d billing_parity   # \password billing_owner_parity, \password billing_app_parity

# reset command: runs as billing_owner_parity through the libpq PG* variables
export PGDATABASE=billing_parity PGUSER=billing_owner_parity PGPASSWORD=<owner_parity> BILLING_APP_ROLE=billing_app_parity
export PROCS_SCHEMA_RESET_COMMAND='printf "DROP SCHEMA IF EXISTS billing CASCADE;\nDROP SCHEMA IF EXISTS billing_migrations CASCADE;\n" | psql -X -q -v ON_ERROR_STOP=1 && services/legacy-billing/db/migrate.sh && psql -X -q -v ON_ERROR_STOP=1 -f services/legacy-billing/db/seed.sql'

# replay: runs as billing_app_parity through the DB_* variables
DB_HOST=<address> DB_PORT=5432 DB_NAME=billing_parity DB_USER=billing_app_parity DB_PASSWORD=<app_parity> \
DB_SSLMODE=verify-full DB_SSLROOTCERT=$PWD/rds-global-bundle.pem \
  uv run --with 'psycopg[binary]==3.2.9' --with pyyaml==6.0.2 procs/harness/schema_parity.py \
    --label rds --expect-user billing_app_parity --require-tls \
    --baseline-report procs/reports/schema-parity-original.json
#   expect: plans 5/5, rating 8/8, invoicing 6/6, dunning 5/5;
#           Schema parity rds: PASS=24 FAIL=0 errors=0 -> PASS (report: procs/reports/schema-parity-rds.{md,json})
```

The run refuses to grade (exit 7) if the transcripts' `SOURCE_SHA` or
`FIXTURE_SHA`, or migrations 0001–0005, no longer match the procedure
sources. Tenant 1's three seeded periods raise on every platform. They are
reported, not graded, and must match the baseline (see `procs/README.md`).
Attach `schema-parity-rds.md` to the change record.

When the run passes, drop the scratch database. Approval: none, it is only
scratch data.

```bash
PGUSER=billing_admin PGPASSWORD=<master> psql -X -d billing <<'SQL'
DROP DATABASE billing_parity;
DROP ROLE billing_app_parity;
DROP ROLE billing_owner_parity;
SQL
```

## Step 5: Freeze, dump, restore, verify (cutover window)

Approval: **A2** before the freeze starts.

Plan for an outage lasting the rehearsed dump + restore + verify time plus
margin. During the freeze, billing pages and the `CALL billing.sp_*` writes
are unavailable.

**5.1 Freeze writes on the source.**

1. Stop every legacy-billing app instance and any job that calls the billing
   procedures.
2. Block new writes, even ones from a stray client:
   ```sql
   -- on the source, as its owner
   ALTER DATABASE <source_db> SET default_transaction_read_only = on;
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity
    WHERE datname = '<source_db>' AND pid <> pg_backend_pid();
   ```
   Note: the source app runs as a superuser, which could still override this
   with `SET`. Stopping the app is the real freeze, and this setting is a
   backstop.
3. Check that nothing else is connected: `SELECT usename, application_name,
   client_addr, state FROM pg_stat_activity WHERE datname = '<source_db>'`
   returns only your own session.

**5.2 Take the source baseline** with the fingerprint from the
prerequisites. Keep the output as `source-baseline.txt` and attach it to the
change record.

```bash
PGOPTIONS='-c TimeZone=UTC -c DateStyle=ISO,MDY -c IntervalStyle=postgres' \
  psql -X -tA -h <source_host> -d <source_db> -U <source_user> -f billing-fingerprint.sql > source-baseline.txt
```

Also capture the outputs of the read-only functions for later comparison:
`fn_list_plans()`, `fn_overdue_accounts(current_date)`, and for 3–5 sample
tenants `fn_entitlement(<tenant>, current_date)` and `fn_invoice_preview(<tenant>,
<period_start>, <period_end>)` for the current period. Save them as
`source-readonly.txt`.

**5.3 Dump the source** (data only, `billing` schema only):

```bash
pg_dump -h <source_host> -d <source_db> -U <source_user> \
  --format=custom --data-only --schema=billing --no-owner --no-privileges \
  --file=billing-<yyyymmddhhmm>.dump
pg_restore --list billing-<yyyymmddhhmm>.dump | grep 'TABLE DATA'   # expect 11 entries, parents before children
```

Keep the dump file in access-controlled, encrypted storage until the source is
decommissioned. It contains billing data.

**5.4 Restore into the target** as `billing_owner`, in a single transaction:

```bash
PGUSER=billing_owner pg_restore -h <address> -d billing \
  --data-only --no-owner --no-privileges --single-transaction --exit-on-error \
  billing-<yyyymmddhhmm>.dump
```

- The schema already exists from `migrate.sh`. No DDL, ownership or grants
  come from the dump, so the `billing_migrations` ledger and the
  `0006_app_grants.sql` privileges stay as they are.
- Foreign keys stay enabled. A data-only archive restores tables in dependency
  order, and the schema has no circular FKs, so `--disable-triggers` (which
  needs superuser) is not used.
- There are no sequences, so no `setval` is needed.
- If the restore fails, the single transaction leaves the target empty. Fix
  the cause and rerun. The source has not been changed.

**5.5 Verify the target.** Run the same fingerprint on the target and compare:

```bash
PGOPTIONS='-c TimeZone=UTC -c DateStyle=ISO,MDY -c IntervalStyle=postgres' \
  PGUSER=billing_owner psql -X -tA -h <address> -d billing -f billing-fingerprint.sql > target-after-restore.txt
diff source-baseline.txt target-after-restore.txt && echo "fingerprint: MATCH"
```

All of the following must hold before the go/no-go call:

- `diff` is empty, so all 11 tables have the same row count and content hash.
- The read-only function outputs from 5.2, rerun on the target **as
  `billing_app`**, are identical to `source-readonly.txt`. This also proves
  the runtime grants.
- `SELECT version, sha256 FROM billing_migrations.applied ORDER BY version` on
  the target lists 0001–0006, and their sha256 values match the files at the
  release commit.
- Step 4's `schema-parity-rds` report is PASS for this release commit.

Only read-only functions are run against the target. Do not call any
`sp_*` there for verification, because they write billing data.

## Step 6: Switch `DB_*` settings

Approval: **A3** (go/no-go). This is the point where the target starts taking
writes that the source never sees.

Change the app environment wherever it is defined. Today that is the
`legacy-billing` service in the Compose file; a future deploy manifest would
hold the same values.

| Setting | Before (record actual values) | After |
|---|---|---|
| `DB_HOST` | source host | Terraform `address` |
| `DB_PORT` | `5432` | Terraform `port` (`5432`) |
| `DB_NAME` | source db | Terraform `db_name` (`billing`) |
| `DB_USER` | `billing` | `billing_app` |
| `DB_PASSWORD` | source password | unset |
| `DB_PASSWORD_SECRET_ARN` | unset | ARN of the `billing_app` secret from the prerequisites |
| `DB_PASSWORD_CACHE_SECONDS` | `300` | `300` |
| `DB_SSLMODE` | unset (`prefer`) | `verify-full` |
| `DB_SSLROOTCERT` | unset | unset (selects the baked `/etc/ssl/certs/rds-global-bundle.pem`) or set explicitly |
| `DB_CONNECT_TIMEOUT` | `10` | `10` |
| `AWS_REGION` | n/a | region of the secret (needed by the `boto3` secret lookup) |

Then start the app, attaching the client security group to its pods, and
smoke-test it:

- `/health` returns `UP`.
- `/plans` matches `fn_list_plans()` from `source-readonly.txt`.
- One read-only entitlement page per sample tenant renders.
- On the target, `SELECT usename, ssl FROM pg_stat_activity JOIN pg_stat_ssl
  USING (pid) WHERE datname = 'billing'` shows only `billing_app` with
  `ssl = t`.

Then re-enable the jobs that call the billing procedures.

Right after the switch, save a target fingerprint (`target-at-switch.txt`,
same command as 5.5). The rollback step needs it to find writes made after the
switch.

## Rollback

The source stays intact and frozen (`default_transaction_read_only = on`)
until decommission (step 7). Rolling back means pointing the app back at it.

**Before step 6** (anything fails in steps 1–5): restart the app with the
recorded old settings and lift the freeze:

```sql
ALTER DATABASE <source_db> RESET default_transaction_read_only;
```

The target can stay as it is for another attempt (truncate it as
`billing_owner` before the next restore) or be destroyed (A5). No approval is
needed beyond the A2 already given for the window.

**After step 6** (an issue found in production on the target):

1. Stop the app and jobs, so nothing writes to the target.
2. Fingerprint the target and diff it against `target-at-switch.txt`.
   - **No difference:** the target took no writes. Restore the old `DB_*`
     values, run the `RESET` above and restart. Nothing is lost.
   - **Differences:** the target holds billing writes (invoices, plan changes,
     dunning) that the source lacks. Pointing back would drop them. Export the
     changed rows from the target (`pg_dump --data-only --schema=billing` into
     a separate file) and get **A4** to choose one of these:
     - Re-apply those business operations on the source after the rollback.
     - Accept the loss.
     - Roll forward and fix the issue on the target instead.

     Don't merge the two databases by hand without that decision.
3. Record the decision and the evidence (fingerprint diffs, exported rows) in
   the change record.

The rollback window lasts until the A6 sign-off. After the source is
decommissioned, rollback means restoring from that final backup.

## Step 7: Decommission the source (no earlier than the agreed soak period)

Approval: **A6**.

Run this after at least one complete billing cycle (rating, invoicing and
dunning) on the target, or after whatever soak period A6 sets.

1. Take a final backup or snapshot of the source and keep it according to the
   billing records-retention policy.
2. Remove the source credentials from the app environment and the secret
   store.
3. Delete the source database or instance.
4. Delete the cutover dump files once the retention owner agrees.

Steps 3 and 4 are the only actions in this runbook that cannot be undone.

## Zero-downtime alternative: AWS DMS

Use DMS when the freeze in step 5 is not acceptable. Steps 1–4 and 6 stay the
same; DMS replaces 5.1–5.4:

- **Source:** logical decoding is required (`wal_level = logical`, or
  `rds.logical_replication = 1` if the source is RDS). The DMS user needs
  replication rights (superuser, or `rds_replication` on RDS). All 11 tables
  have primary keys, which CDC requires.
- **Target:** tables come pre-created by `migrate.sh`. Set the task's target
  table preparation mode to *Do nothing*, so DMS does not recreate tables and
  drop the constraints, grants and routines. DMS does not migrate functions or
  procedures; `migrate.sh` already created them.
- **Network:** attach `client_security_group_id` to the DMS replication
  instance. The target SG admits nothing else.
- **Cutover:** run a full load, then CDC until the lag is near zero. After that
  you still need a few-minute write stop: stop the app, wait for CDC lag 0,
  run 5.5, switch `DB_*` and stop the task.
- **Rollback:** the same as above, with one caveat. Reverse CDC from target to
  source is a separate task, and it has to be set up before the switch if you
  want rollback without data loss.
- **Cost:** DMS adds a replication instance and more moving parts for a schema
  of this size. That is why it is the alternative here, not the default.

## Approvals

Roles, not people. Map them to named approvers in the change record before
the window. Each approval is recorded in the change record with the evidence
listed.

| # | Step | Why it needs approval | Approvers | Evidence required |
|---|---|---|---|---|
| A1 | Step 1 `terraform apply` | Creates billable AWS resources (RDS, KMS key, secret, log groups) in the shared VPC | Platform/infrastructure owner; cost owner | Reviewed `terraform plan` output |
| A2 | Step 5 write freeze | Customer-facing billing outage for the window | Billing service owner; change approver (CAB) | Rehearsal timings; steps 1–4 complete; local proofs and `schema-parity-rds` PASS |
| A3 | Step 6 switch | After this, writes go only to the target and the source diverges | Billing service owner; database owner/DBA | Empty fingerprint `diff`; matching read-only outputs; migration ledger 0001–0006 |
| A4 | Rollback after writes on the target | Pointing back drops or re-applies real billing transactions | Billing data owner (finance); billing service owner | Target fingerprint diff against `target-at-switch.txt`; exported changed rows |
| A5 | Destroying the target (abandoned cutover) | Needs `deletion_protection=false` first; RDS keeps the final snapshot `<name>-final` | Platform/infrastructure owner; billing service owner | Confirmation that no production writes went to the target |
| A6 | Step 7 decommission of the source | Irreversible; ends the rollback window | Billing service owner; billing data owner (records retention); database owner/DBA; security (credential and data disposal) | Soak period complete; final source backup retained |
