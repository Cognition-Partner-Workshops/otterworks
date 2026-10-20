# OtterWorks Industry Solutions — Insurance (Commission Pay)

The legacy **Commission Pay** application fixture: an insurance commission
system whose business logic lives entirely in **Oracle stored procedures**
(PL/SQL), with a companion **OLAP** star schema fed by a PL/SQL ETL. This is
the database-centric *before state* that stored-procedure modernization demos
extract from.

## Why Oracle Database Free

`container-registry.oracle.com/database/free` (Oracle Database Free, 23ai+) is
Oracle's no-cost developer edition: real PL/SQL packages, object types,
materialized views, and `SQL*Plus` — full stored-procedure fidelity with zero
license cost. Resource limits (2 CPU threads, 2 GB SGA, 12 GB user data) are
irrelevant for this fixture. It runs locally in Docker Compose, bound to
`127.0.0.1` only, in a disposable per-namespace project.

## Layout

```
services/industry-solutions/insurance/
  db/startup/  00_init.sh                 — idempotent init orchestrator (auto-run by the image on boot)
  db/setup/    01_users.sql               — schema/user creation (run by 00_init.sh as SYSTEM)
  db/oltp/     01_tables.sql              — agents, products, policies, rates, splits, ledger, audit
               02_seed.sql                — deterministic test data
               03_commission_pkg.sql      — COMMISSION_PKG: all business rules (PL/SQL)
  db/olap/     01_star_schema.sql         — dim_agent / dim_product / dim_period / fact_commission
               02_etl_pkg.sql             — DW_ETL_PKG.LOAD_COMMISSION_FACTS + summary MV
  db/olap/scenario/                       — 2025 month-end baseline driver (make insurance-scenario)
  db/olap/golden/                         — golden CSV export (make insurance-golden)
  dbt/commission_dw/                      — dbt-postgres port of COMMISSION_DW on PostgreSQL 16 (make insurance-pg-up / insurance-dbt-build)
  dbt/commission_dw/golden/               — committed golden baseline CSVs
  db/tests/    run_tests.sql              — OLTP suite (12+ cases, PASS/FAIL, non-zero exit on failure)
               run_olap_tests.sql         — ETL/star-schema suite (run after the OLTP suite)
```

Two schemas inside the `FREEPDB1` pluggable database:

- **`COMMISSION_PAY`** (OLTP) — the transactional system of record. All
  business rules are in `COMMISSION_PKG`; there is deliberately no application
  tier duplicating them.
- **`COMMISSION_DW`** (OLAP) — the analytics warehouse: star schema, idempotent
  `MERGE`-based ETL reading the OLTP schema, and the
  `MV_AGENT_COMMISSION_SUMMARY` materialized view.

## The business rules (all in `COMMISSION_PKG`)

- **`upsert_commission_rate`** — create/supersede a commission rate for a
  product (default) or a specific agent. Rates must be in `(0, 50]`; the prior
  open rate for the same scope is closed the day before the new one begins
  (effective-dated history, never deleted); suspended/terminated agents are
  rejected; every change is audit-logged.
- **`end_commission_rate`** — close the open rate for a scope.
- **`set_commission_splits`** — the **split-commission allocation** across two
  or more agents: replaces a policy's allocation atomically; requires at least
  one agent, no duplicates, all agents `ACTIVE`, each percentage in `(0, 100]`,
  and the percentages summing to **exactly 100.00**.
- **`resolve_rate`** — the rate in force for (product, agent, date); an
  agent-specific rate wins over the product default.
- **`calculate_policy_commission`** — writes the monthly ledger: per agent,
  `annual_premium / 12 × rate_pct / 100 × split_pct / 100`, rounded to cents
  per agent row. Re-running a period replaces its rows (idempotent). Lapsed or
  cancelled policies and policies without a split allocation are rejected.

## Run it

From the repo root (NS is any alphanumeric namespace; ports are derived from
it so concurrent namespaces never collide):

```bash
make insurance-up NS=dev     # pulls Oracle Free, first boot takes a few minutes
make insurance-test NS=dev   # runs the OLTP suite, then the OLAP suite
make insurance-down NS=dev   # tears down and deletes the data volume
```

Expected test output ends with:

```
OLTP TESTS: ALL PASS
...
OLAP TESTS: ALL PASS
```

Connect ad hoc (port = `51521 + crc32(NS) % 1000`, printed by
`make help`-style inspection or `docker ps`):

```bash
docker exec -it otterworks-insurance-dev-insurance-oracle-1 \
  sqlplus commission_pay/commission_pay@localhost:1521/FREEPDB1
```

## Month-end scenario (warehouse baseline)

The seed leaves `commission_ledger` empty. `make insurance-scenario NS=dev`
runs a deterministic month-end year on a **fresh** fixture:

1. `olap/scenario/01_month_end_ledger.sql` (COMMISSION_PAY) adds
   scenario-only reference data (product `COMM-GL`/COMMERCIAL, policies
   `POL-2025-0101` and `POL-2025-0102`, a HOME-PLUS rate superseded from
   2025-07-01, an agent override on COMM-GL), then calls
   `calculate_policy_commission` for every policy that is `IN_FORCE`, issued
   on or before the month-end and split-allocated, for 2025-01..2025-12. It
   re-runs 2025-12 for POL-2025-0102 after a split correction and checks the
   edge cases (3-way split cent rounding, override, supersession, re-run,
   every line of business).
2. `olap/scenario/02_load_warehouse.sql` (COMMISSION_DW) runs
   `dw_etl_pkg.load_commission_facts(NULL, ...)`, a COMPLETE refresh of
   `MV_AGENT_COMMISSION_SUMMARY`, and reconciles MV totals with the ledger.
3. `olap/scenario/03_mv_report.sql` prints the MV per period, in full, and
   an order-independent fingerprint.

Each step ends `... ALL PASS`. The scenario is idempotent (a second run gives
identical MV contents) and refuses to run once `make insurance-test` has
changed the fixture; `make insurance-test` still passes after it.

After the scenario, `make insurance-golden NS=dev` exports the pinned baseline
(source extract, naturally keyed facts, full MV) as CSV into
`dbt/commission_dw/golden/`; `make insurance-golden-check NS=<ns>` rebuilds a
fresh fixture, regenerates and diffs byte-for-byte against the committed files,
then tears the fixture down. See `dbt/commission_dw/golden/README.md`.

## dbt-postgres target (PostgreSQL 16)

The warehouse is being ported to dbt on PostgreSQL 16 in `dbt/commission_dw/`
(see its README):

```bash
make insurance-pg-up NS=dev        # postgres:16, loopback only, port 57432 + crc32(NS) % 1000
make insurance-dbt-build NS=dev    # dbt deps, debug, build
make insurance-pg-down NS=dev      # stop and drop the volume
```

## Fixture boundary

This is a local, disposable fixture: loopback-only port bindings, per-namespace
Compose projects and volumes, and fixed well-known fixture credentials. It is
intentionally **not** deployed to Helm/EKS or any shared environment. A real
modernization target must add authentication, authorization, tenant scoping,
and secret management at the service edge — none of which exist in the legacy
database-centric design, which is part of the point.
