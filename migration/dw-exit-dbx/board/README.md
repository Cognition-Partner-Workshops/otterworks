# Migration board

```json
{
  "spark_ref": "pr-2740",
  "spark_commit": "40a2465c7eb30777a634abfa698d3a2e7ca17e47",
  "waves": {
    "1": 87,
    "2": 70,
    "3": 100,
    "4": 16
  },
  "kinds": {
    "BTEQ": 25,
    "FastLoad": 22,
    "PowerCenter mapping": 20,
    "PowerCenter session": 20,
    "PowerCenter workflow": 3,
    "Spark job": 30,
    "Spark shared": 6,
    "TPT": 20,
    "batch job": 6,
    "consumer": 8,
    "decommission": 1,
    "hidden consumer": 4,
    "macro": 6,
    "procedure": 4,
    "scheduler": 3,
    "table": 84,
    "view": 11
  },
  "loc": 8028,
  "counters": {
    "teradata_objects": 105,
    "powercenter_mappings": 20,
    "spark_executor_hours": 0.206092502
  },
  "spark_applications": 30
}
```

Wave 1: retirement and Delta foundations. Wave 2: ingestion. Wave 3: transformations, shared Spark runtime and orchestration. Wave 4: compatibility, consumer signoff and decommission. Spark dbt hints are transforms (wave 3), not ingestion.

Executor-hours are the measured History Server baseline over 30 applications, not an annual estimate. Non-Spark batch jobs have NULL hours: unmeasured, not zero.

```sql
/* run=dbx-d1111 act=assess step=counter */
SELECT
  count_if(source_system = 'teradata' AND kind IN ('table','view','macro','procedure')) AS teradata_objects,
  count_if(kind = 'PowerCenter mapping') AS powercenter_mappings,
  sum(executor_hours) AS spark_executor_hours
FROM cpw.dbx_d1111_control.migration_control
WHERE status NOT IN ('migrated', 'retired');
```
