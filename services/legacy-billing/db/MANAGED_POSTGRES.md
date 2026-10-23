# legacy-billing database: managed PostgreSQL inventory

Read-only inventory of the `billing` schema in `db/schema.sql`, `db/procs/*.sql`
and `db/seed.sql`, checked against what a managed service such as Amazon RDS for
PostgreSQL allows. Inventory taken from `demo-appassess` at `f57a3f76b`. No code
or live database was changed.

**Verdict:** the schema, all 12 routines and the seed load and run unchanged as
a non-superuser database owner. Nothing in the DDL needs superuser, an untrusted
language, a server-side file or a C extension. The work left for RDS is
operational: roles and grants, the version target, TLS, the session time zone
and the reset path (see [Managed-service findings](#managed-service-findings)).

## Load order and current runtime

`docker-compose.procs.yml` loads the files through `docker-entrypoint-initdb.d`
in this order, and `procs/harness/record.py` (`DB_FILES`) replays the same list:

1. `schema.sql` 2. `procs/plans.sql` 3. `procs/rating.sql`
4. `procs/invoicing.sql` 5. `procs/dunning.sql` 6. `seed.sql`

Today the service runs only on `postgres:16` from that Compose file, connecting
as `billing`, the image's bootstrap superuser (`POSTGRES_USER`). It has no Helm
chart, ECR image or api-gateway route. The shared RDS instance
(`infrastructure/terraform/modules/database/main.tf`) is PostgreSQL **15.7**
with the default parameter group and master user `otterworks_admin`.

## Schema

| Object | Kind | Notes |
|---|---|---|
| `billing` | schema | Created by `schema.sql` (`CREATE SCHEMA billing`). Needs `CREATE` on the database. |

## Tables (11)

All use built-in types only (`uuid`, `text`, `boolean`, `integer`,
`numeric`, `date`, `timestamptz`), with `PRIMARY KEY`, `UNIQUE`, `CHECK` and
`FOREIGN KEY` constraints. No sequences, identity or generated columns,
partitioning, triggers, rules, indexes beyond constraint indexes, tablespaces or
`UNLOGGED`. Primary keys are supplied by the caller (literal UUIDs in the seed,
`md5(...)::uuid` in the procedures), so no `uuid-ossp` or `pgcrypto` is needed.
Minimum version: any supported release (nothing newer than 8.4).

| Table | FKs to | Notable constraints |
|---|---|---|
| `billing.tenants` | none | `name` unique; `status IN ('active','suspended')` |
| `billing.plans` | none | `code` unique; tier, non-negative fee, units and rate checks |
| `billing.subscriptions` | tenants, plans | status check; `ends_on >= starts_on`; `suspended_on >= starts_on` |
| `billing.usage_events` | tenants | `units > 0`; `kind IN ('api','storage','compute')` |
| `billing.rating_periods` | tenants | unique `(tenant_id, period_start)`; `period_end >= period_start` |
| `billing.rating_results` | rating_periods, subscriptions | non-negative unit and amount checks |
| `billing.invoices` | tenants, rating_periods | non-negative totals; status check |
| `billing.invoice_lines` | invoices (`ON DELETE CASCADE`) | unique `(invoice_id, line_no)`; `line_type` check |
| `billing.credit_notes` | tenants | `amount > 0`; `0 <= remaining_amount <= amount` |
| `billing.dunning_attempts` | tenants, invoices | unique `(invoice_id, attempt_no)`; status check |
| `billing.notifications` | tenants | unique `(tenant_id, kind, sent_at)`; kind check |

## Functions and procedures (12)

All are `SECURITY INVOKER` (the default; no `SECURITY DEFINER`), have no `SET`
clauses and are written in `sql` or `plpgsql`, both trusted. Neither uses dynamic
SQL (`EXECUTE`), `COPY`, `dblink`/`postgres_fdw`, large objects or
`pg_read_file`-style server file access.

| Routine | Kind | Language | File | Writes | Constructs that set the minimum version | Min PG |
|---|---|---|---|---|---|---|
| `fn_list_plans()` | function | sql | plans.sql | none | `RETURNS TABLE` | 8.4 |
| `fn_entitlement(uuid, date)` | function | sql | plans.sql | none | `RETURNS TABLE` | 8.4 |
| `sp_change_plan(uuid, uuid, date)` | procedure | plpgsql | plans.sql | subscriptions | `CREATE PROCEDURE` | **11** |
| `fn_usage_rating(uuid, date, date)` | function | plpgsql | rating.sql | none | `RETURNS TABLE`, `%ROWTYPE`, `RETURN QUERY` | 8.4 |
| `fn_usage_summary(uuid, date, date)` | function | sql | rating.sql | none | `RETURNS TABLE` | 8.4 |
| `sp_finalize_rating(uuid, date, date)` | procedure | plpgsql | rating.sql | rating_periods, rating_results | `CREATE PROCEDURE`, `ON CONFLICT ... DO UPDATE` | **11** |
| `fn_invoice_preview(uuid, date, date)` | function | plpgsql | invoicing.sql | none | `RETURNS TABLE`, calls `fn_usage_rating` | 8.4 |
| `fn_invoice_lines(uuid)` | function | sql | invoicing.sql | none | `RETURNS TABLE` | 8.4 |
| `sp_issue_invoice(uuid, date, date)` | procedure | plpgsql | invoicing.sql | invoices, invoice_lines, credit_notes (+ via `sp_finalize_rating`) | `CREATE PROCEDURE`, `CALL` from PL/pgSQL, `ON CONFLICT` | **11** |
| `fn_overdue_accounts(date)` | function | sql | dunning.sql | none | `RETURNS TABLE` | 8.4 |
| `sp_schedule_dunning(date)` | procedure | plpgsql | dunning.sql | dunning_attempts | `CREATE PROCEDURE`, `ON CONFLICT ... DO NOTHING` | **11** |
| `sp_suspend_overdue(date)` | procedure | plpgsql | dunning.sql | tenants, subscriptions, notifications | `CREATE PROCEDURE` | **11** |

**Minimum PostgreSQL for the whole schema: 11**, because of the five `CREATE
PROCEDURE` objects and `CALL` (the app issues `CALL billing.sp_*` from
`app/app.py`, and `sp_issue_invoice` calls `sp_finalize_rating`). No procedure
commits or rolls back inside its body, so nothing relies on transaction control
in procedures. No PG 12+ to 16 features are used, so the RDS target of 15.7 runs
the code as written.

Built-in functions used: `md5`, `round`, `sum`, `count`, `max`, `COALESCE`,
`LEAST`, `GREATEST`, `extract(isodow ...)`, date arithmetic and
`interval '3 months'`. All are core and available on RDS.

## Seed

`seed.sql` contains 11 plain `INSERT ... VALUES` statements, one per table. It
has no `COPY ... FROM` server file, `\copy`, `SET`, `ALTER` or `GRANT`, and it
loads over a normal client connection.

## Extensions

None created. The only extension present after a load is `plpgsql`, which ships
installed and trusted in every PostgreSQL database, RDS included.

## Roles and grants

None defined. There is no `CREATE ROLE`, `GRANT`, `REVOKE`, `ALTER ... OWNER`
or `ALTER DEFAULT PRIVILEGES` anywhere in the billing SQL. Every object is owned
by whoever runs the load, and the app connects as that same role (`DB_USER`,
default `billing`). The runtime privileges the app needs, worked out from
`app/app.py` and the routine bodies, are:

- `USAGE` on schema `billing`
- `EXECUTE` on the 7 functions and 5 procedures. PostgreSQL grants this to
  `PUBLIC` by default, but schema `USAGE` still limits who can call them.
- On tables (the routines run as `SECURITY INVOKER`, so the caller needs these):
  `SELECT` on all 11; `INSERT, UPDATE` on `subscriptions`, `rating_periods`,
  `rating_results` and `invoices`; `UPDATE` on `tenants` and `credit_notes`;
  `INSERT` on `dunning_attempts` and `notifications`; `INSERT, DELETE` on
  `invoice_lines`. `ON CONFLICT ... DO UPDATE` needs both `INSERT` and `UPDATE`.

## Managed-service findings

There are no hard blockers. Each item below is something a move to RDS has to
decide, and none of them needs a code change to the routines.

1. **Superuser today, not on RDS.** Compose runs the app as the image superuser.
   RDS gives no real superuser (the master user only has `rds_superuser`). The
   load and runtime were checked as a plain `NOSUPERUSER NOCREATEDB
   NOCREATEROLE` role that owns its database, and that works. Plan a dedicated
   owner role for the migration and a runtime role with the grants above. Don't
   reuse `otterworks_admin`.
2. **No role or grant DDL.** Because of the previous point, the move has to add
   the role, `GRANT` and `ALTER DEFAULT PRIVILEGES` statements itself. They
   don't exist yet, and the app currently depends on being the schema owner.
3. **Version mismatch: local 16, RDS 15.7.** Nothing in the code needs more than
   11, so 15.7 is fine. Parity recordings (`procs/transcripts`) were produced on
   16, though, so re-run `make procs-parity` against a 15.x database before the
   cut-over.
4. **Session time zone affects results.** `occurred_at::date`,
   `issued_at::date` and `p_period_end::timestamptz` / `p_as_of::timestamptz`
   depend on the session `TimeZone`. The Compose image and the RDS default
   parameter group both use UTC, so they match today. Pin `TimeZone=UTC` (on
   the role or in a custom parameter group) so the shared instance can't drift.
5. **TLS is not configured in the client.** `psycopg.connect` in `app/app.py`
   sets no `sslmode`, so libpq's default `prefer` applies. RDS for PostgreSQL
   15 and later defaults to `rds.force_ssl=1`, so 15.7 requires TLS. `prefer`
   still connects over TLS, but it never verifies the server certificate. Use
   `sslmode=verify-full` with the RDS CA bundle.
6. **The reset path is destructive.** `procs/harness/record.py`
   `reset_database()` runs `DROP SCHEMA IF EXISTS billing CASCADE` and reloads
   all files. On RDS this works for the schema owner and needs no superuser,
   but the harness must only ever point at a disposable per-run database, never
   the shared instance's tenant databases.
7. **CREATE privilege for the schema.** `CREATE SCHEMA billing` needs `CREATE`
   on the target database. Within a per-tenant `otterworks_<ID>` database owned
   by `otterworks_admin`, grant it explicitly to the owner role.
8. **`md5()` for IDs.** Deterministic keys come from `md5(...)::uuid`. This
   works on RDS. It would only fail on a FIPS-restricted build (not the RDS
   default), and it's worth noting if the target is ever GovCloud/FIPS.

Statements RDS would refuse, searched for and **not found**: `CREATE EXTENSION`
of untrusted/C extensions, `LANGUAGE c` / `plpythonu` / `plperlu`,
`COPY ... FROM '<file>'` / `COPY ... TO PROGRAM`, `pg_read_file` /
`lo_import`, `ALTER SYSTEM`, `CREATE TABLESPACE`, `SET session_replication_role`,
`ALTER ROLE ... SUPERUSER`, `SECURITY DEFINER` routines and `SET` of
superuser-only GUCs.

## Seed-data observation (unrelated to the managed service)

`sp_finalize_rating` derives `v_period_id = md5(tenant || period_start)::uuid`
and upserts `rating_periods` `ON CONFLICT (tenant_id, period_start)`. For the
three periods that `seed.sql` already holds for tenant 1 (2025-11, 2025-12 and
2026-01, with literal ids `40000000-...`), the upsert keeps the seeded id. The
following `rating_results` insert then fails its FK, so `sp_finalize_rating` /
`sp_issue_invoice` raise for those periods. This happens the same way on any
PostgreSQL and is not a managed-service issue. It's recorded here so a parity
failure on RDS isn't blamed on the platform.

## How this was checked

On a throwaway local PostgreSQL 14.24 cluster (`apt install postgresql`;
Docker Hub and the ECR public mirror were rate-limited, so 15.7 couldn't be
pulled), as a role created `LOGIN NOSUPERUSER NOCREATEROLE NOCREATEDB` that
owns database `billing_t`:

```
loaded schema.sql / procs/plans.sql / procs/rating.sql / procs/invoicing.sql / procs/dunning.sql / seed.sql
rolsuper|rolcreatedb = f|f
SELECT count(*) FROM billing.fn_list_plans()                    -> 3
CALL billing.sp_issue_invoice(tenant 4, 2026-07-01, 2026-07-31) -> ok
CALL billing.sp_change_plan(...) / sp_schedule_dunning('2026-03-07') -> ok
pg_extension                                                     -> plpgsql
tables in schema billing                                         -> 11
DROP SCHEMA billing CASCADE (as owner)                           -> ok
```

Version minimums come from PostgreSQL release history: `CREATE PROCEDURE` and
`CALL` arrived in 11, `ON CONFLICT` in 9.5 and `RETURNS TABLE` in 8.4. 14
matches the 15.7 target on every construct used here.

## Migrations

Legacy billing uses plain numbered SQL files and a `psql` runner. Flyway is
used by JVM services elsewhere in the repository, but this service is Python
and has no JVM toolchain. Migrations 0001–0005 are verbatim copies of the source
files at this commit; the parity harness and Compose stack continue to load the
original files. Land later routine changes as new migrations rather than
editing an applied migration.

| Finding | Resolution |
|---|---|
| 1. Superuser runtime | `bootstrap/roles.sql` creates separate non-superuser owner and app roles. |
| 2. Missing role and grant DDL | The bootstrap creates roles; migration `0006_app_grants.sql` applies runtime grants. |
| 3. PostgreSQL version | The target is a dedicated RDS for PostgreSQL 16 instance (`infrastructure/terraform/legacy-billing-db/`), matching local `postgres:16`; the shared 15.7 instance is not used. |
| 4. Session time zone | Role settings pin UTC; `migrate.sh` also pins `search_path` and `TimeZone` with `PGOPTIONS`. |
| 5. TLS | Set `PGSSLMODE=verify-full` and `PGSSLROOTCERT` in the libpq/psycopg environment. |
| 6. Reset path | The runner has no reset or drop path; harness reset remains for disposable local databases only. |
| 7. Database `CREATE` | The bootstrap grants `CREATE` on the target database to the owner role. |
| 8. `md5()` identifiers | No change; record the FIPS-build caveat if the target changes. |
