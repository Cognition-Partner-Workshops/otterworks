# Direct conversion checkpoint

Run on the existing SQL warehouse with environment credentials:

```sh
python -m warehouse.databricks.billing.run
python -m warehouse.databricks.parity --label v1-direct --spec warehouse/databricks/billing/parity_spec.json
```

`direct.sql` rebuilds the selected chain from **baseline staging tables only**.
The monthly invoice procedure is expanded into its ordered DML statements;
its local `run_day` is the literal business date. Core loads are CTAS from
staging (STRING text, original numeric/date types); subsequent INSERT and MERGE
retain those types. No case folding, padding, truncation or SET deduplication
is implemented. QUALIFY retains the source's incomplete ordering.

Variables: BUSINESS_DATE=20261109, MONTH_START=20261101,
MONTH_END=20261201, PERIOD_START_INT=1261001, PERIOD_END_INT=1261031.

Literal working forms for Spark SQL:

- DATE-to-INT and DATE division use `unix_date(date)` (epoch days), Spark's
  direct integer-date representation, **not** Teradata's encoded integer date.
- `date_format(date,'YYYY-MM')` was rejected with
  `INCONSISTENT_BEHAVIOR_CROSS_VERSION.DATETIME_PATTERN_RECOGNITION`;
  the working pattern is `yyyy-MM`. No legacy session policy is enabled.
- `ZEROIFNULL(x)` becomes `coalesce(x,0)`; `MOD` becomes `%`.
- `date - 1` is retained literally.

Macros are SQL table functions named `<subject>__<macro>_fn`; corresponding
`<subject>__<macro>` Delta tables materialize their outputs for baseline params.
The parity spec includes every created table/view (functions are compared via
those materialized outputs). Results and SQL receipts are under ~/dbx-evidence.
