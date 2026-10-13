# Credit review: run `sfm-20261013-lv`

Read as `OW_UBW_SFM_20261013_LV_VIEWER` (role READER) on 2026-10-13, from
`INFORMATION_SCHEMA.WAREHOUSE_METERING_HISTORY`, `INFORMATION_SCHEMA.QUERY_HISTORY_BY_WAREHOUSE` (9,896 queries), `INFORMATION_SCHEMA.TASK_HISTORY`
(10 task runs), `SHOW TASKS` and `SHOW WAREHOUSES`.

## Billed credits: the first day

The run's objects were created 2026-10-12 17:46 PDT, so the run is one day old. Its first day was migration
work: dbt builds, gate runs, raw loads and one manual task-graph run. All tasks were suspended and none fired on its
schedule. These are the warehouse's billed credits from
`INFORMATION_SCHEMA.WAREHOUSE_METERING_HISTORY`, read as READER after the platform team granted
`MONITOR USAGE` and imported privileges on `SNOWFLAKE`:

| Hour (PDT, 2026-10-12) | Compute | Cloud services | Total |
|---|---:|---:|---:|
| 17:27-18:27 | 0.000 | 0.002 | 0.002 |
| 18:27-19:27 | 0.225 | 0.056 | 0.281 |
| 19:27-20:27 | 1.166 | 0.192 | 1.358 |
| 20:27-21:27 | 0.766 | 0.135 | 0.901 |
| **First day** | **2.157** | **0.385** | **2.542** |

`ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY`, on clock hours and still catching up, shows 2.495 credits so far.
Cloud services are billed only for the part above 10% of the account's daily compute. `QUERY_ATTRIBUTION_HISTORY`
has no rows for the run yet, because it lags by hours, so the split by category and model below is a proportional attribution.

The warehouse is `STANDARD_GEN_2`. Query timings put it up for about 5,449 s over 24 resumes, counting each
resume until 60 s after its last query with a 60 s minimum. That makes the billed 2.157 compute credits an effective
**1.43 credits per running hour**. The projections below use that measured rate, not the 1 credit/hour list rate for X-Small.

## First day by category (billed compute, attributed by query time)

The total is billed. The split shares it out by each category's share of the estimated warehouse time.

| Category | Queries | Execution s | Attributed credits |
|---|---:|---:|---:|
| dbt model builds (`dbt build`) | 2,348 | 445 | 0.74 |
| Gate and other DBT-user selects | 5,774 | 319 | 0.53 |
| Gate ledger reads and writes | 821 | 202 | 0.34 |
| Raw loads (PUT / COPY) | 250 | 116 | 0.19 |
| Other DBT-user statements (Snowpark deploy, grants, DDL) | 438 | 113 | 0.19 |
| Task graph (one manual run) | 75 | 72 | 0.12 |
| Snowsight READER | 28 | 20 | 0.03 |
| dbt tests, bootstrap | 161 | 5 | 0.01 |

By model, the largest were `build_mart_tenant_usage` (33 s over 182 statements), `rollup_storage_daily` (32 s),
`rollup_audit` (31 s) and `rollup_usage_events` (29 s), each about 0.05 credits. Those four were rebuilt
more often than the rest during the divergence work. Every other model came in under 0.025 credits.
Repeated migration builds account for all of this; none of it reflects the steady-state cost of any model.

## Steady state, from the task schedules

One manual graph run took 40 seconds from `UBW_NIGHTLY_LOAD` to the end of `UBW_LOG_RUN` (load 2.3 s, dims 9.5 s,
storage 4.4 s, facts 11.6 s, marts 10.3 s, log 2.9 s). On a warehouse with a 60 second auto-suspend,
each resume is billed for the work plus about 60 seconds of idle time.

| Task | Schedule before | Schedule after | Resumes/day before | Resumes/day after |
|---|---|---|---:|---:|
| `UBW_NIGHTLY_LOAD` graph (load, dims, storage, facts, marts, log) | 02:30 daily | 02:30 daily (unchanged) | 1 | 1 |
| `UBW_HOURLY_AUDIT` (`rollup_audit`, `build_mart_audit`) | minute 05, hourly | retired; both models run in the nightly graph | 24 | 0 |
| `UBW_WEEKLY_RETENTION` | Sun 03:00 | unchanged | 1/7 | 1/7 |
| `UBW_WEEKLY_CAPACITY_FORECAST` | Mon 06:15 | unchanged | 1/7 | 1/7 |
| `UBW_MONTHLY_OVERAGE` | day 1 04:00 | unchanged | 1/30 | 1/30 |

`UBW_HOURLY_AUDIT` ran more often than its data changes. Audit events reach Snowflake only through
`pkg_audit` → `RAW.STG_AUDIT_EVENTS`, which `UBW_LOAD_RAW` loads once a night, so 23 of the 24 hourly runs
re-derive the same rows. `UBW_BUILD_FACTS` and `UBW_BUILD_MARTS` already run `rollup_audit` and
`build_mart_audit` right after that load. The weekly and monthly tasks match the source cadence
(`jobs.yaml`, `crontab.legacy`) and rerate different business dates (week end, `EOMONTH`), so they stay.

## Credits per day, before and after

The first day is billed. Every other row is a projection from the schedules at the measured 1.43 credits per running
hour. A graph resume is 40 s (measured) and an hourly audit resume is about 8 s (estimated, since the task never ran),
each plus about 60 s idle before suspend.

| Day | Before | After | Change |
|---|---:|---:|---:|
| First day 2026-10-12, billed (migration build, no scheduled tasks) | 2.54 | n/a | n/a |
| Projected weekday (nightly graph + 24 hourly audits) | 0.69 | 0.040 | -94% |
| Projected Sunday / Monday / 1st of month (adds one weekly or monthly task) | 0.71 | 0.068 | -90% |
| Projected 30-day month | ~20.8 | ~1.5 | -93% |

One finding matters on its own. With the schedules as they were, resuming the graph would have
used about 20.8 credits a month against the bootstrap default quota of 5. The resource monitor
would have suspended the warehouse, nightly load included, around day 7.

## Models: what could be incremental

- All 16 date-keyed fact and mart models, plus `log_run` and `stg_billing_usage_events`, are already
  `incremental` with `delete+insert` on `business_date`, the way the legacy procedures DELETE and
  INSERT one `@business_date`.
- The 7 dimensions are `table` because they are full snapshots of full-reload extracts. The largest,
  `dim_document` (39,982 rows) and `dim_file` (24,993 rows), are small; the whole `UBW_BUILD_DIMS` step for all seven took 9.5 s. An incremental merge would still
  scan the whole staging view, and it would risk keeping rows the source deleted. Either way the run fits inside
  the 60 seconds billed per resume, so it saves no credits. No model was changed, and the gate's models are
  the ones from PR #1978.

## Clustering

The largest scan in the history is 38 MB. The biggest RAW table is about 12 MB and every mart is under 4 MB.
Each table holds a handful of micro-partitions, so pruning has nothing to prune. No clustering keys
were added.

## Warehouse shape

X-Small with a 60 second auto-suspend is the right shape. X-Small is the smallest size. The history has
0 seconds of queued overload, and the longest task step is 11.6 s (`UBW_BUILD_FACTS`), so a larger size would
just burn more credits per second for the same 40 seconds. Every resume is billed for at least 60 seconds,
so a shorter auto-suspend saves at most the idle tail of one resume a day after this change.
Two further steps would need the builder, and this session did neither:

- Serverless tasks (`EXECUTE MANAGED TASK`) would drop the 60 second minimum for a 40 second graph.
- `ALTER WAREHOUSE ... AUTO_SUSPEND = 30` would trim the idle tail.

ENGINEER has `OPERATE`/`MONITOR` on the warehouse but not `MODIFY`.

## Resource monitor

The projected steady state is about 1.5 credits a month. The one real day billed 2.54 credits, and
it was a full migration rebuild. The quota stays at **5 credits a month**: one steady-state month (1.5),
plus one more rebuild day like the first (2.5), plus about 20% headroom. Notify at 75% (3.75 credits) is new, so a
rebuild day raises a notice before anything is suspended, and suspend stays at 100%. `SHOW RESOURCE MONITORS` returns no rows to
READER even with the new grants, so the live monitor's current quota could not be read. Applying this
means re-running `bootstrap.py up` (default `--credit-quota 5`) through `account.sql` with the builder
credentials, which this session does not use.

## Parity after the change

The task graph was recreated with `tasks.py create`: the tasks are still suspended, and `UBW_HOURLY_AUDIT` is dropped. Then
`make sfm-gate RUN=$UBW_RUN DATE=2026-09-30` was run once:

```
Parity PASS=15 DIVERGE=10 PENDING=0
```

This is the same line, with the same ten explained divergences, as the last gate in PR #1978. No model SQL changed, and
`ledger.json` changed only in `generated_at`.
