# audit_daily_summary — sfg1120

## Decision: migrate, not retire

`jobs/py/lake_compaction_audit.py:4` reads
`/opt/lake/audit/audit_daily_summary`. It is still a `legacy` registration
(`jobs/registry/lake_compaction_audit.yaml:5`), scheduled by
`cron.d/lake_compaction_audit:1` and `etl/crontab:30` on the base branch.
Repository-wide searches found no reader of `sfx_audit.SPARK_AUDIT_SUMMARY`.
The warehouse dbt summary instead reads the AUDIT_EVENT source; similarly named
Informatica/warehouse summary tables are separate outputs.

PR #3263's small-profile template registration, Kubernetes settings, cron and
wrapper removal are reused. Its date-partition write is deliberately not reused:
the still-active compactor reads the entire output root, so keeping multiple
dates would change its input. Preserve the legacy unpartitioned full refresh;
use the transactional JDBC refresh helper for the second sink. Cache both the
single explicitly typed landing scan and the coalesced summary, and use two
shuffle partitions. No shared template or Compose changes are needed.

## Local measurements

Spark 3.5.3; 200,000 landing rows per fact table, fixture seed 1110; same estate,
sequential runs. Runtime and executor-hours come from `measure.py spark --app`
against `http://localhost:18080`, excluding driver lifetime. These are application
runtimes, not spark-submit wall-clock time or billed hours.

| Phase | Application | Runtime seconds | Executor-hours |
|---|---|---:|---:|
| Before 1 | app-20261120170012-0000 | 13.412 | 0.014751944 |
| Before 2 | app-20261120170026-0001 | 12.918 | 0.014225278 |
| Before 3 | app-20261120170040-0002 | 14.755 | 0.015503611 |
| **Before median** | | **13.412** | **0.014751944** |
| After 1 | app-20261120170131-0003 | 9.682 | 0.002823333 |
| After 2 | app-20261120170142-0004 | 8.221 | 0.002260000 |
| After 3 | app-20261120170152-0005 | 14.290 | 0.005761111 |
| **After median** | | **9.682** | **0.002823333** |

Median runtime decreased 27.8%; median executor-hours decreased 80.9%.
After run 3 still showed allocation variance despite caching; all runs are
included rather than selecting only the fastest run. Every measured application
had zero failed tasks and zero spill. The packaged baseline remains unchanged
(14.229 seconds, 0.015961667 executor-hours).

The requested tag `sfg1120` is used in the branch and Docker project
`sfg1120-spark-audit-daily-summary`. `warehouse/run_config.py` only accepts
`sfx`-prefixed RUN_TOKEN values, so the estate was started with the explicit
Docker project name, without changing the shared run-token validator.
The initial 120-second Make startup timed out; the same Compose project completed
with `--wait-timeout 900`. `warehouse/run_config.py` was copied into `/opt/warehouse`
on the master and both workers for template imports.

## Verification

Legacy JDBC rows were captured before editing. After all three template runs,
both the ordered JDBC rows and all four columns of the parquet rows match those
42 legacy rows exactly. The lake remains an unpartitioned full refresh.

`make sfx-spark-test`: 55 tests, OK; packaged baseline matches 30 applications.
The job-specific Scala check covers counts, distinct actors, null actors, dates,
empty input and a missing-input error. It runs through
`tests/test_audit_daily_summary.py` as part of that target.

This is local-estate verification only; Kubernetes deployment and visual checks
were not performed.
