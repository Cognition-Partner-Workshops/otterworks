# usage-meter

Per-tenant, per-period usage meter for the OtterWorks billing estate. It mirrors
`pkg_rating.fn_usage_rating` (`services/legacy-billing/db/oracle/packages/03_pkg_rating.sql`)
so meter totals equal what legacy rating bills.

## Shape

```
Lakebase mig-invoicing-w1 / ow_tp_invoicing      (SELECT-only, read-only transaction)
  -> meter.py snapshot -> build/snapshot/<table>/<table>.csv
  -> databricks fs cp  -> /Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/
  -> sql/00_load_snapshot.sql -> ow_tp.ow_tp_usage_meter.ow_tp_snap_*   (Delta)
  -> sql/02_meter.sql         -> ow_tp.ow_tp_usage_meter.ow_tp_usage_meter
  -> synced table (SNAPSHOT)  -> Lakebase mig-usage-meter, databricks_postgres.ow_tp_usage_meter.ow_tp_usage_meter_synced
```

All SQL runs on warehouse `565cd2fd713738c4`. Nothing writes to Lakebase directly; the
managed synced table is the only path. `mig-usage-meter` is a child of `production`
(w1 has an expiry, so it can't have children) and is short-lived.

## Run

```bash
databricks experimental aitools tools query --warehouse 565cd2fd713738c4 --output json --file sql/01_schema.sql   # once
python meter.py snapshot
databricks fs cp -r build/snapshot dbfs:/Volumes/ow_tp/ow_tp_usage_meter/ow_tp_snap_files/ --overwrite
databricks experimental aitools tools query --warehouse 565cd2fd713738c4 --output json --file sql/00_load_snapshot.sql
databricks experimental aitools tools query --warehouse 565cd2fd713738c4 --output json --file sql/02_meter.sql
databricks postgres create-synced-table ow_tp.ow_tp_usage_meter.ow_tp_usage_meter_synced --json '{"spec":{"source_table_full_name":"ow_tp.ow_tp_usage_meter.ow_tp_usage_meter","primary_key_columns":["tenant_id","period_start"],"branch":"projects/ow-tp-billing/branches/mig-usage-meter","postgres_database":"databricks_postgres","scheduling_policy":"SNAPSHOT","create_database_objects_if_missing":true,"new_pipeline_spec":{"storage_catalog":"ow_tp","storage_schema":"ow_tp_usage_meter"}}}' --output json   # once
python meter.py parity                                   # Delta vs Lakebase, row for row
python meter.py compare --tenant "Tenant One" --oracle-dsn 44.213.30.5:1521/FREEPDB1
```

`compare` reads `OW_TP_ORACLE_RO_DSN` (JSON or EZConnect `user/password@host:port/service`);
`--oracle-dsn` overrides the address. Needs `psycopg[binary]` and `oracledb`.

`databricks.yml` deploys the paused job `ow_tp_usage_meter` (load, compute, sync). The
snapshot and upload steps stay manual.

## Rating semantics (from pkg_rating)

- Periods: every `rating_periods` row, plus calendar months with usage no period covers.
- Subscription: latest overlapping one (`starts_on DESC`); no subscription means no plan figures.
- Used units: events whose day falls inside the period, inclusive (`TO_CHAR(..., 'YYYYMMDD')`).
- Rollover: `rating_results.rollover_units` from periods starting in the prior 3 months,
  capped at `2 * included_units`.
- Billable: `GREATEST(used - rollover - included, 0)`; first 101 units at the plan rate,
  the rest at 1.5x; overage rounded to cents.
- Status 20 subscriptions suspended inside the period: billable and overage pro-rated by
  remaining days.
