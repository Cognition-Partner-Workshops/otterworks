# Data platform before: legacy warehouse and analytics

Run the Teradata emulator using the [warehouse quickstart](../README.md).
The legacy path runs on the local PostgreSQL-backed Teradata emulator; it does not
need a cloud account. Informatica runs through its local PowerCenter emulator
and Spark uses JDBC. Finance BI and the partner handoff consume batch files.

## Nightly finance reporting

1. FastLoad/TPT replace the staging tables from the dated landing files.
2. [Account history](scripts/billing/load_account_history.bteq) reads
   `STG_CUSTOMER_ACCOUNT` before the usual Type 1 core reload. The separately
   maintained Type 2 table has one row per customer and effective start date.
   A MERGE expires a changed status or currency; an INSERT opens the new version.
   Dates are start-inclusive/end-exclusive, with `9999-12-31` denoting the
   open version. A missing customer in a feed is not a closure; send a changed
   status to record one.
3. The report step [exports an as-of rollup](scripts/billing/14_account_history_extract.bteq)
   to `warehouse/exports/account_status_YYYYMMDD.psv`. Import this headerless
   pipe-delimited file in the [Finance workbook](../../consumers/bi/README.md) as
   business date (ISO), status, currency, account count; empty fields are unknown.
   The workbook consumes a file, not a database connection. The whole dated
   extract is rebuilt on rerun.

[The example crontab](jobs/crontab.example) is for a UTC batch host with the repo
at `/opt/otterworks`. Bootstrap the local warehouse first so the virtualenv and
`warehouse/exports` exist; arrange for yesterday's feeds to land before 01:15 UTC.
Install the crontab manually as the batch user, adjusting the path and namespace.
The 02:15 job prepares a partner extract; adjust `TD_PG_PORT` if the namespace
changes. `TD_USER` is the BTEQ audit label, not
the PostgreSQL login. The example contains no secrets; never put passwords or
private keys into crontab.

For the checked-in demo date, run
`make sfx-teradata-up NS=sfx-d1110-before ROWS_PER_TABLE=2000 BUSINESS_DATE=20261109`
and inspect `warehouse/exports/account_status_20261109.psv`. If the feed or a
step fails, inspect the batch log, fix the input, and rerun the latest date
with `make sfx-teradata-run NS=sfx-d1110-before BUSINESS_DATE=20261109`
(use the applicable date in operation). Do not overlap with a scheduled run.
History changes and its business-date marker commit together. The loader can
replace the latest day's changes, but refuses older dates after a later date
has been loaded; to replay older inputs, use a separate demo namespace. An
older as-of extract can be regenerated from retained history without reloading
that day. There is no inferred account history before the first loaded feed.

## Optimization assessment

| Area | Evidence and opportunity |
| --- | --- |
| Batch I/O and compute | [FastLoad/TPT loader](bteq/load.py) replaces staging; [account reload](scripts/billing/01_load_accounts.bteq) and [monthly invoice procedure](procedures/monthly_invoice.sql) rewrite broad datasets. Measure scans and elapsed time with the chain's step timings and DBQL; move to keyed deltas and affected-period recomputation while preserving late corrections and balanced journals. |
| Scheduling and recovery | [Daily chain](jobs/daily_chain) is a serial list of subprocesses and stops at the first failure. The cron sample is time-based and manual. Model explicit feed readiness, upstream dependencies, per-step retries and backfills instead of rerunning the whole chain. |
| ETL maintenance and licensing | [PowerCenter exports and runner](../../etl/informatica/README.md) duplicate mapping logic across proprietary XML, parameter files, and the emulator; [licence inventory](../../etl/informatica/licence.yaml) identifies which features keep the runtime in use. Prioritize mapped jobs by dependency count and actual run frequency, and check that replacements preserve accepted and rejected rows. |
| Spark throughput | [Spark runtime](../../etl/spark/jobs/py/common/runtime.py) defaults to a single JDBC read partition and overwrite output. Use [recorded event logs](../../etl/spark/history/baseline.json) to select expensive jobs, then benchmark projected/filtered and partitioned reads and incremental writes. Do not size jobs off the small fixture alone. |
| Analytics scans and semantics | The [partner BTEQ extract](../../consumers/partner-extract/sql/partner_invoice_extract.bteq) aggregates payments across the warehouse for one day's invoices. Test narrowing payment aggregation to eligible invoice keys, then compare a shared, incrementally maintained balance against the legacy outputs; preserve currency and aging semantics. |
| Governance and retirement | Reconcile the [consumer registry](../../consumers/registry.yaml) with the [DBQL reader inventory](dbql/consumer_reads.bteq) to identify unmanaged connections. Add owned table-to-report lineage, retention and least-privilege controls for files that are no longer visible to the warehouse. |

These are code-based opportunities, not measured savings. The committed DBQL
fixture is synthetic. It includes the account-history rollout on the final
fixture day; it is not production usage evidence.
