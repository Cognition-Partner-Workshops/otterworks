# Slice-0 synced tables (CODES, PLANS)

Reference data reaches the Lakebase run branch as synced tables from the Delta mirror
`ow_tp.mig_unt19_20261030_slice_0`, one `databricks postgres create-synced-table` per table:

```
databricks postgres create-synced-table <LAKEBASE_CATALOG>.mig_unt19_20261030_slice_0.codes --json @codes.json
databricks postgres create-synced-table <LAKEBASE_CATALOG>.mig_unt19_20261030_slice_0.plans --json @plans.json
```

`<LAKEBASE_CATALOG>` is the Unity Catalog registration of the run branch's Postgres database
(`databricks postgres create-catalog mig_unt19_20261030_lakebase --json @catalog.json`). At the time of
the slice-0 PR no catalog was registered for the `ow-tp-billing` project and the migration principal
lacks `CREATE CATALOG` on the metastore, so `load_lakebase.py` filled `codes` and `plans` as plain tables
from the same mirror (identical rows: the snapshot is frozen). Once the catalog exists, drop the two plain
tables, run the commands above, and `load_lakebase.py` leaves the synced tables alone.
