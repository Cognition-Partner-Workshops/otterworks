# legacy-billing on managed PostgreSQL (Amazon RDS): inventory

The plan is to keep the `billing` schema and its 12 stored entrypoints **in the
database** and to move that database from the Compose `postgres:16` container to
a dedicated **Amazon RDS for PostgreSQL 16** instance with `rds.force_ssl=1`. This
file lists everything in `services/legacy-billing` that RDS would refuse or
behave differently on, plus what would differ on PostgreSQL 15.

This is a read-only analysis. Nothing in `db/schema.sql`, `db/procs/`, `db/seed.sql`,
`app/` or `procs/transcripts/` changes here, and no database was provisioned. All
`path:line` references are to the commit this file is added on (base
`demo-appassess` @ `f57a3f76b`). Paths are relative to the repository root.

## Summary

| Area | Verdict on RDS PostgreSQL 16 | Action for the next billing tickets |
|---|---|---|
| Superuser features, extensions, untrusted languages, `SECURITY DEFINER` | **None used.** Loads and runs as a non-superuser owner | None |
| Ownership and grants | Works only because the app connects as the **owner**; there are no `GRANT`s at all | Create an owner role and a separate app role with explicit grants |
| `search_path` | No dependence: every object is schema-qualified | Optionally pin `search_path` on the roles anyway |
| Loading the schema | Compose loads it through `docker-entrypoint-initdb.d`; RDS has no such hook | Ship an explicit, ordered load step |
| Time zone | **Result-bearing.** 3 of 24 transcripts change under a non-UTC session | Pin `timezone=UTC` on the DB/roles, never set `PGTZ` |
| `DateStyle` | **Result-bearing.** Deterministic ids are built from `date::text`; psycopg cannot read non-ISO output | Pin `DateStyle='ISO, MDY'` on the DB/roles |
| Collation / `ORDER BY` on text | No observed dependence (`LOCALE 'C'` gives 24/24 identical) | Create the DB with the same locale anyway |
| `now()` / clock functions | **None used**: every date comes from a parameter | None |
| Numeric rounding | `numeric` only, no floats; identical on 15 and 16 | Keep columns and arithmetic `numeric` |
| TLS (`rds.force_ssl=1`) | `db_connect()` connects encrypted but **unverified** (libpq default `sslmode=prefer`) | Add `sslmode`/`sslrootcert` knobs, `verify-full` against the RDS CA bundle |
| PostgreSQL 15 vs 16 | Transcripts 24/24 identical on 15.19 and 16.15; raw numeric output identical | Stay on 16; notes below if 15 is ever chosen |

## What was checked locally

The checks ran on throwaway local containers (`mirror.gcr.io/library/postgres:16`
= 16.15 and `:15` = 15.19). Each run re-recorded all 24 scenarios with the unchanged
harness (`procs/harness/record.py --output-dir <scratch dir>`, so the committed
transcripts were never touched) and compared the output field by field with
`procs/transcripts/` (ignoring only the `rerecord_reason` bookkeeping key). RDS
defaults come from the read-only call `aws rds describe-engine-default-parameters`
for the `postgres16` and `postgres15` families in us-east-1.

| # | Check | Before (Compose `postgres:16`, recorded transcripts) | After (variant) | Result |
|---|---|---|---|---|
| 1 | Re-record on 16.15 as the Compose superuser `billing` | 24 transcripts | 24/24 identical | identical |
| 2 | Re-record on 16.15 as a `NOSUPERUSER NOCREATEDB NOCREATEROLE` owner of its own DB (RDS-like) | 24 transcripts | 24/24 identical | identical |
| 3 | Re-record on 15.19 as the superuser | 24 transcripts | 24/24 identical | identical |
| 4 | Re-record on 15.19 as a non-superuser owner | 24 transcripts | 24/24 identical | identical |
| 5 | Re-record on 16.15, DB created `LOCALE 'C' TEMPLATE template0` | DB `en_US.utf8`, libc provider | 24/24 identical | identical |
| 6 | Re-record on 16.15 with the role's `timezone = 'America/Chicago'` | session `Etc/UTC` | 21/24; DUNNING-001 `days_overdue` [27, 15] became [28, 16]; DUNNING-004/005 `sent_at` `2026-02-28T00:00:00Z` became `2026-02-28T06:00:00Z` | **failed** (so the RDS TZ has to stay UTC) |
| 7 | Re-record on 16.15 with the role's `DateStyle = 'SQL, DMY'` | `ISO, MDY` | aborted at DUNNING-004: psycopg `can't parse timestamptz with DateStyle 'SQL, DMY'` | **failed** (so DateStyle has to stay ISO) |
| 8 | Catalog of the 12 entrypoints after load as non-superuser | n/a | 7 `plpgsql` + 5 `sql`, all `lanpltrusted`, `prosecdef = f`, no `proconfig`; only extension is `plpgsql` | identical to the ticket's count |
| 9 | Raw `fn_invoice_preview` (tenants 4, 5) and `fn_usage_rating` (tenant 2) text output, 15.19 vs 16.15 | 16.15 output | 15.19 output byte-identical (e.g. tax line `6.3116625000000000`) | identical |
| 10 | Unmodified `app.db_connect()` against a server that rejects non-TLS (`hostnossl ... reject`, the effect of `rds.force_ssl=1`) | Compose: no TLS (`ssl=False`) | default: connects, `ssl=True TLSv1.3`, cert not verified; `PGSSLMODE=disable`: rejected by `pg_hba`; `PGSSLMODE=verify-full` without a root cert: refused by libpq | accepted difference (encrypted, but verification needs a config change; see TLS section) |
| 11 | Unmodified `app.db_connect()` against Compose-style server (`ssl=off`) with `PGSSLMODE=require` | connects without TLS | fails: `server does not support SSL` | accepted difference (local stacks keep `prefer`/`disable`) |
| 12 | Least-privilege app role, no grants / `USAGE` only / `+SELECT` / `+INSERT,UPDATE,DELETE` | n/a (app is the owner) | `permission denied for schema billing` / `permission denied for table plans` / reads work, `CALL sp_suspend_overdue` denied on `tenants` / everything works; `DROP SCHEMA billing` still denied (`must be owner`) | matches the grants listed below |
| 13 | RDS default parameter group `postgres16` | Compose server: `TimeZone=Etc/UTC`, `DateStyle=ISO, MDY` | `timezone=UTC` (system), `datestyle` unset (engine default `ISO, MDY`), `rds.force_ssl=1`, `ssl_min_protocol_version=TLSv1.2`, `search_path` unset | identical for TZ/DateStyle; TLS is the accepted difference in rows 10-11 |

Rows 6 and 7 are deliberately misconfigured variants that show which settings carry
results; they fail and are reported as failed.

## 1. Superuser features, extensions, languages, `SECURITY DEFINER`

Nothing in the billing database needs `rds_superuser`, let alone a real superuser:

- No `CREATE EXTENSION`. The deterministic ids use the built-in `md5()`, not
  `pgcrypto`/`uuid-ossp`: `services/legacy-billing/db/procs/plans.sql:60`,
  `services/legacy-billing/db/procs/rating.sql:103`, `services/legacy-billing/db/procs/rating.sql:127`,
  `services/legacy-billing/db/procs/invoicing.sql:85-86`, `services/legacy-billing/db/procs/invoicing.sql:109`,
  `services/legacy-billing/db/procs/dunning.sql:46`, `services/legacy-billing/db/procs/dunning.sql:77`.
- Only trusted languages: `LANGUAGE sql` at `services/legacy-billing/db/procs/plans.sql:10`, `:28`,
  `services/legacy-billing/db/procs/rating.sql:85`, `services/legacy-billing/db/procs/invoicing.sql:69`,
  `services/legacy-billing/db/procs/dunning.sql:9`; `LANGUAGE plpgsql` at
  `services/legacy-billing/db/procs/plans.sql:47`, `services/legacy-billing/db/procs/rating.sql:18`, `:100`,
  `services/legacy-billing/db/procs/invoicing.sql:15`, `:82`, `services/legacy-billing/db/procs/dunning.sql:21`, `:54`.
  That is 5 `sql` + 7 `plpgsql`, the 12 entrypoints the README lists
  (`services/legacy-billing/README.md:16-19`). `plpgsql` is preinstalled on RDS.
- No `SECURITY DEFINER`, no `SET` clauses on functions, no `ALTER SYSTEM`, no
  `COPY ... FROM` a server file, no event triggers, no `pg_cron`, no tablespaces.
  All 12 functions are `SECURITY INVOKER`, so **the caller needs the table privileges**
  (section 2).
- `CREATE SCHEMA billing` (`services/legacy-billing/db/schema.sql:1`) needs `CREATE` on the
  database, which the database owner has. Check rows 2 and 4 load the whole schema,
  procedures and seed as a `NOSUPERUSER NOCREATEDB NOCREATEROLE` owner.

The superuser bit is only an accident of the Compose image: `POSTGRES_USER: billing`
(`docker-compose.procs.yml:8`) makes `billing` the cluster superuser, and both the app
(`docker-compose.procs.yml:37`) and the recording harness (`procs/harness/record.py:45`)
connect as it.

## 2. Ownership, grants, `search_path`

**Ownership.** Every table, index, function and the schema itself are owned by whoever
runs the load (row 8: all `billing_owner`). There are no `GRANT`/`REVOKE`/`ALTER ... OWNER`
statements anywhere in `services/legacy-billing/db/`. The app works only because it
connects as that owner (`services/legacy-billing/app/app.py:17`, default user `billing`).
On RDS the owner should not be the master user and the app should not be the owner.
Proposed roles:

| Role | Attributes | Owns / granted |
|---|---|---|
| RDS master user | `rds_superuser` | creates the two roles and the database; nothing else |
| `billing_owner` | `NOLOGIN` (used by migrations via `SET ROLE`) | owns database `billing`, schema `billing`, all tables and the 12 entrypoints |
| `billing_app` | `LOGIN` | `CONNECT` on the DB; `USAGE` on schema `billing`; `SELECT, INSERT, UPDATE, DELETE` on all tables in `billing`; `EXECUTE` on the 12 entrypoints (PUBLIC has it by default; revoke from PUBLIC and grant explicitly) |

Row 12 shows each grant is needed: `USAGE` for the schema, `SELECT` for the read
functions, `INSERT/UPDATE/DELETE` for the procedures (`sp_suspend_overdue` updates
`billing.tenants`, `services/legacy-billing/db/procs/dunning.sql:69-71`; `sp_issue_invoice` deletes
`billing.invoice_lines`, `services/legacy-billing/db/procs/invoicing.sql:102`). Set
`ALTER DEFAULT PRIVILEGES FOR ROLE billing_owner IN SCHEMA billing` so later objects
get the same grants. PostgreSQL 16 restricts `CREATEROLE` (a role can only administer
roles it has `ADMIN` on), so run role setup as the master user.

**Harness.** `reset_database()` runs `DROP SCHEMA IF EXISTS billing CASCADE` and reloads
every file (`procs/harness/record.py:102-107`). That needs schema ownership (row 12:
`billing_app` is refused), and it must never point at the RDS database: recordings stay
on the disposable Compose stack.

**`search_path`.** Nothing depends on it. Every table and routine reference is
`billing.`-qualified (e.g. `services/legacy-billing/db/procs/rating.sql:46`,
`services/legacy-billing/db/procs/invoicing.sql:93`, `:104`), the `%ROWTYPE` declarations are qualified
(`services/legacy-billing/db/procs/rating.sql:21-22`, `services/legacy-billing/db/procs/invoicing.sql:18`), and
the app calls qualified names (`services/legacy-billing/app/app.py:56-146`). Built-ins (`md5`,
`round`, `LEAST`, `GREATEST`, `extract`) resolve from `pg_catalog`, which is always
searched first. `public` is not used, so the PostgreSQL 15+ `REVOKE CREATE ON SCHEMA
public FROM PUBLIC` (row 12, last probe) does not matter. RDS leaves `search_path` at
the engine default (row 13).

**Load step.** Compose applies the files through `/docker-entrypoint-initdb.d` in a
fixed order (`docker-compose.procs.yml:13-18`). RDS has no init hook, so the next ticket
needs an explicit load in the same order: `schema.sql`, `plans.sql`, `rating.sql`,
`invoicing.sql`, `dunning.sql`, then `seed.sql` only for non-production databases. The
tables must exist before the procedure files, because `LANGUAGE sql` bodies are validated
at `CREATE` time (`check_function_bodies` is unset in the RDS group, so the engine default
`on` applies). `plpgsql` cross-calls such as invoicing into rating
(`services/legacy-billing/db/procs/invoicing.sql:32`, `:93`) are resolved at run time.

## 3. Time zone

The procedures never read the clock; the time zone matters through casts between
`date` and `timestamptz`, which use the session `TimeZone`:

| Where | Cast | Effect of a non-UTC session |
|---|---|---|
| `services/legacy-billing/db/procs/rating.sql:46`, `:90` | `occurred_at::date BETWEEN ...` | usage events near midnight UTC move to another day, so into another period |
| `services/legacy-billing/db/procs/dunning.sql:11`, `:16` | `issued_at::date` | `days_overdue` and the overdue filter shift by a day (row 6: DUNNING-001 `[27, 15]` became `[28, 16]`) |
| `services/legacy-billing/db/procs/dunning.sql:63` | `issued_at::date <= p_as_of - 14` | the 14-day suspension cut-off shifts |
| `services/legacy-billing/db/procs/dunning.sql:78`, `:83` | `p_as_of::timestamptz` | `notifications.sent_at` is stored at local midnight (row 6: `06:00:00Z`), and the `NOT EXISTS` dedupe compares in that same zone |
| `services/legacy-billing/db/procs/rating.sql:131`, `services/legacy-billing/db/procs/invoicing.sql:97` | `p_period_end::timestamptz` | `rating_results.created_at` / `invoices.issued_at` stored at local midnight |

The seed writes UTC literals (`services/legacy-billing/db/seed.sql:42-51`, `:63-67`, `:73-77`,
`:96`), and the harness converts `timestamptz` to UTC before writing
(`procs/harness/record.py:78-82`), so the transcripts are only reproducible with a UTC
session. Compose sessions are `Etc/UTC` (row 1); the RDS `postgres16` group defaults
to `timezone=UTC` (row 13), so the default matches. It can still be changed in three
places, all of which have to stay UTC: the parameter group, `ALTER DATABASE/ROLE ... SET
timezone`, and the client's `PGTZ` env var, which libpq honours even though `db_connect()`
never sets it (row 10, last attempt). Pin `ALTER DATABASE billing SET timezone = 'UTC'`
so a later parameter-group edit cannot change billing results.

No `now()`, `current_date`, `current_timestamp`, `clock_timestamp()` or `localtime` appears
in `services/legacy-billing/db/` or `services/legacy-billing/app/app.py`. Every "as of"
date is a parameter, with app defaults hard-coded (`services/legacy-billing/app/app.py:68`, `:106-107`, `:134`).
`extract(isodow FROM v_next)` on a `date` (`services/legacy-billing/db/procs/dunning.sql:38`, `:40`) and
`p_period_start - interval '3 months'` compared with a `date`
(`services/legacy-billing/db/procs/rating.sql:54`) do not depend on the time zone.

## 4. `DateStyle` (deterministic ids)

Deterministic primary keys are `md5()` of a string that includes `date::text`:
`p_effective_on::text` (`services/legacy-billing/db/procs/plans.sql:60`), `p_period_start::text`
(`services/legacy-billing/db/procs/rating.sql:103`, `services/legacy-billing/db/procs/invoicing.sql:85`) and
`p_as_of::text` (`services/legacy-billing/db/procs/dunning.sql:77`). `date::text` follows `DateStyle`:
`2026-02-01` under ISO, `01/02/2026` under `SQL, DMY`. A different `DateStyle` changes every
period, invoice and notification id, so they no longer match rows written under ISO.
Rating periods are upserted on `(tenant_id, period_start)` and keep their old id
(`services/legacy-billing/db/procs/rating.sql:117`, `services/legacy-billing/db/schema.sql:45`), while
`sp_issue_invoice` recomputes the period id and upserts the invoice on the id alone
(`services/legacy-billing/db/procs/invoicing.sql:85-86`, `:100`) against a foreign key to
`rating_periods(id)` (`services/legacy-billing/db/schema.sql:64`). A `DateStyle` change between
runs would break that id chain; this was not exercised beyond row 7, which aborts first.
Scenario probes also recompute ids from ISO literals (`procs/scenarios/invoicing/003.yaml:18`). psycopg also refuses to parse non-ISO
`timestamptz` output (row 7). The RDS default is the engine default `ISO, MDY` (row 13);
pin it with `ALTER DATABASE billing SET datestyle = 'ISO, MDY'`.

## 5. Collation and text ordering

- Text `ORDER BY`: `ORDER BY monthly_fee, code` (`services/legacy-billing/db/procs/plans.sql:15`; `code`
  only breaks ties and seeded fees are distinct, `services/legacy-billing/db/seed.sql:15-17`) and
  `ORDER BY u.kind` (`services/legacy-billing/db/procs/rating.sql:92`; values limited to lower-case ASCII
  `api`/`storage`/`compute` by `services/legacy-billing/db/schema.sql:37`). Lower-case ASCII sorts
  the same under `C` and `en_US.UTF-8`.
- Other orderings are on `uuid`, `date`, `timestamptz` or `integer`, which don't use a
  collation: `services/legacy-billing/db/procs/dunning.sql:17`, `:32`, `services/legacy-billing/db/procs/invoicing.sql:74`,
  `:131`, `services/legacy-billing/db/procs/plans.sql:38`, `services/legacy-billing/db/procs/rating.sql:36`, `:112`.
- Text unique indexes: `tenants.name` and `plans.code` (`services/legacy-billing/db/schema.sql:5`, `:12`).
  Equality doesn't depend on a deterministic collation, but the btree order does.
  Building the RDS database with a fresh load (or `pg_dump`/restore, which rebuilds
  indexes) avoids carrying an index built under another glibc.

Row 5 (`LOCALE 'C'`) gave 24/24 identical. Compose creates the DB as `en_US.utf8` with the
libc provider (row 1). Create the RDS database with an explicit `LOCALE 'en_US.UTF-8'
TEMPLATE template0` so the choice is written down rather than inherited.

## 6. Numeric rounding

- Money columns are `numeric(12,2)` and the rate is `numeric(12,6)`
  (`services/legacy-billing/db/schema.sql:14`, `:16`, `:57`, `:66-68`, `:78`, `:86-87`). All arithmetic stays
  in `numeric`: literals `1.5` and `0.0825` (`services/legacy-billing/db/procs/rating.sql:60`,
  `services/legacy-billing/db/procs/invoicing.sql:42`), integer-to-`numeric` casts before division
  (`services/legacy-billing/db/procs/rating.sql:65`, `:69`), and `extract()` returns `numeric` on 14+. No
  `float8`/`real` appears. `round(numeric, n)` rounds half away from zero, and so does the
  implicit coercion on insert into `numeric(12,2)`; this is the same on 15 and 16 (row 9).
- Rounding is behaviour, not a platform difference, but the next tickets must preserve it:
  the two tax lines are `v_tax / 2` unrounded (`services/legacy-billing/db/procs/invoicing.sql:52`, `:54`;
  e.g. `6.3116625000000000`), are rounded per line when stored into `invoice_lines.amount`
  (`services/legacy-billing/db/procs/invoicing.sql:106-113`) and summed after rounding
  (`services/legacy-billing/db/procs/invoicing.sql:115-117`, `:122-124`). The suspension proration uses
  `round(...)::integer` and `round(..., 2)` (`services/legacy-billing/db/procs/rating.sql:64-71`).
- The functions return unconstrained `numeric`, so the scale shown to clients varies
  (`4.01`, `6.3116625000000000`); the app turns `Decimal` into a string without
  re-scaling (`services/legacy-billing/app/app.py:23-24`), and the harness quantizes declared
  decimals to 0.01 half-up (`procs/harness/record.py:68-69`). Raw output was byte-identical
  on 15 and 16 (row 9).

## 7. Connection and TLS (`rds.force_ssl=1`)

`db_connect()` (`services/legacy-billing/app/app.py:12-19`) passes only host, port, dbname, user and
password: no `sslmode`, `sslrootcert`, `connect_timeout` or `application_name`. The harness
has `connect_timeout=5` but no TLS options either (`procs/harness/record.py:40-48`). With `rds.force_ssl=1` (the RDS default for both
families, row 13) the server rejects non-TLS sessions. The libpq default `sslmode=prefer`
still gets through, encrypted, but **without verifying the server certificate** (row 10).
`verify-full` needs the RDS CA bundle on disk: the image is `python:3.12-slim`
(`services/legacy-billing/Dockerfile:1`), and the RDS CAs are not in the system trust store.
Requirements for the next ticket:

- Add optional `DB_SSLMODE` / `DB_SSLROOTCERT` (or a DSN) to `db_connect()`, defaulting to
  today's behaviour so the Compose stack, which has TLS off, keeps working (row 11: `require`
  fails there).
- In the RDS deployment, set `verify-full` with the AWS RDS global CA bundle mounted or baked
  into the image. libpq's `PGSSLMODE`/`PGSSLROOTCERT` env vars work with the unmodified code
  (row 10), but an explicit setting is easier to review.
- Every request opens a new connection (`services/legacy-billing/app/app.py:36`, `:43`). With TLS each
  request now costs a handshake. That is fine at this size, but count it against the
  instance class's `max_connections` (`LEAST({DBInstanceClassMemory/9531392},5000)`).
- The app opens a transaction per request and commits on exit; none of the procedures
  issue `COMMIT`/`ROLLBACK`, so `CALL` inside the driver's transaction is fine on RDS too.
- The local containers authenticate TCP clients with `scram-sha-256`, and the psycopg 3.2.9
  binary wheel connected fine (rows 10-11). The RDS groups leave `password_encryption` to the
  service (`system` source, no value shown), so the next ticket should confirm SCRAM once an
  instance exists.

## 8. PostgreSQL 15 vs 16

Target is 16. On 15.19 vs 16.15 the 24 transcripts are identical (rows 3-4) and so is the raw
numeric output (row 9). Differences that would still matter if 15 were chosen, or when
moving between them:

- **Dump/restore direction.** Compose and the transcripts are on 16 (`docker-compose.procs.yml:5`).
  A dump from 16 is not guaranteed to restore into 15. Keep the RDS major at 16 and
  reload from the SQL files, not from a dump of the container.
- **Minor version.** `postgres:16` is a floating tag (16.15 on this pull); RDS us-east-1 offers
  16.3 to 16.15 and 15.7 to 15.19 (`aws rds describe-db-engine-versions`). Pin the RDS engine
  minor version and the Compose image to the same minor so parity runs compare like with like.
- **Roles.** PostgreSQL 16 changed `CREATEROLE` semantics and added `GRANT ... WITH INHERIT/SET`
  options; the role script in section 2 only uses plain `GRANT`s and runs as the master user,
  so it works on both.
- **Parameter groups.** The RDS `postgres16` default group preloads `pg_tle` alongside
  `pg_stat_statements`; `postgres15` preloads only `pg_stat_statements`. Connection slots kept
  for administrators are `rds.rds_superuser_reserved_connections = 2` on 15 and the core
  PostgreSQL 16 `reserved_connections = 2` on 16. Billing uses none of these.
- **SQL surface.** Nothing in `db/` uses a 16-only feature (SQL/JSON constructors, `IS JSON`,
  non-decimal or underscore numeric literals) or `MERGE` (15+). `CREATE PROCEDURE`/`CALL`,
  `RETURNS TABLE`, `ON CONFLICT` and `%ROWTYPE` are old features.
- **Public schema.** `public` lost default `CREATE` in 15, the same in 16; billing doesn't use it.

## 9. Not covered here

- No RDS instance, parameter group or Terraform. The values above are engine defaults from
  the AWS API, not a provisioned instance.
- `procs/transcripts/` stays the reference recorded on Compose `postgres:16`; any re-record
  against RDS belongs in a later ticket and must not overwrite them.
- `services/billing-service` (the extraction target) is out of scope: the procedures stay in
  the database.
