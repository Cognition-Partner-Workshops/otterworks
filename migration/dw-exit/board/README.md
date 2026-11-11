# Migration board

| Count | Wave 1 | Wave 2 | Wave 3 | Wave 4 |
|---|---:|---:|---:|---:|
| Total | 108 | 51 | 52 | 11 |
| by_kind: bteq | 0 | 12 | 13 | 0 |
| by_kind: catalog | 6 | 0 | 0 | 0 |
| by_kind: fastload | 22 | 0 | 0 | 0 |
| by_kind: macro | 1 | 0 | 5 | 0 |
| by_kind: mapping | 6 | 9 | 5 | 0 |
| by_kind: procedure | 0 | 0 | 4 | 0 |
| by_kind: session | 6 | 9 | 5 | 0 |
| by_kind: table | 45 | 21 | 18 | 0 |
| by_kind: tpt | 20 | 0 | 0 | 0 |
| by_kind: view | 2 | 0 | 0 | 9 |
| by_kind: workflow | 0 | 0 | 1 | 2 |
| by_kind: worklet | 0 | 0 | 1 | 0 |
| by_target: compatibility_view | 0 | 0 | 0 | 9 |
| by_target: dbt_model | 49 | 35 | 25 | 0 |
| by_target: retire | 20 | 0 | 0 | 0 |
| by_target: snowflake_scripting | 39 | 12 | 24 | 2 |
| by_target: snowpark | 0 | 4 | 3 | 0 |

## Licence counters

| Counter | Remaining | Target |
|---|---:|---:|
| teradata_objects | 111 | 0 |
| powercenter_mappings | 20 | 0 |
| spark_executor_hours | 0 | 0 |

PowerCenter annual cost: 412000 USD. Spark: 0 measured executor-hours; no Spark estate on branch yet. Later acts drive remaining counters to zero via MIGRATION_CONTROL status. Consumer repointing (including hidden accounts) and decommission are Wave 4 gates.
