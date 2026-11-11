# Direct conversion checkpoint

Run on the existing SQL warehouse with environment credentials:

```sh
python -m warehouse.databricks.billing.run
python -m warehouse.databricks.parity --label v1-direct --spec warehouse/databricks/billing/parity_spec.json --replace --gaps
python -m warehouse.databricks.billing.run --version fixed
python -m warehouse.databricks.parity --label v2-fixed --spec warehouse/databricks/billing/parity_spec.json --replace --gaps
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

## Ownership and corrected checkpoint

All writes in both versions are billing-owned. Upstream inputs use
`billing__in_users_*` / `billing__in_documents_*`; the spec's `before` field
retains the original baseline name. `--inputs-only` rebuilds just those renamed
inputs. The runner rejects writes outside the billing prefix and never operates
on the sibling content job or its `users__*` / `documents__*` tables.

`fixed.sql` applies source DDL widths: substring for VARCHAR and substring plus
right-padding for CHAR, including generated STORAGE usage rows. SET storage
loads use full-row DISTINCT. Comparison keys use upper(rtrim()) for source
NOT CASESPECIFIC columns, leaving stored values unchanged. Integer-date SQL
functions implement the emulator's date_int/int_date formulas.

The emulator translates grouped text columns to rtrim(CAST(column AS TEXT));
PostgreSQL retains its ICU case-insensitive collation. Its hash aggregate keeps
an encountered group representative rather than uppercasing stored output.
For this ordered staging feed, the conversion selects the first invoice-key
representative with min_by(rtrim(currency_cd),invoice_id), retaining original
case. This is a deterministic representative convention, not a promise to
reproduce arbitrary PostgreSQL physical-order changes; it is checked against
the captured source outputs by exact parity.

QUALIFY's source ordering is genuinely nondeterministic for timestamp ties.
The interim approved target ordering is VERSION_TS DESC, VERSION_NO DESC,
VERSION_ID DESC. Exact parity is **not** relaxed: its red rows remain visible.
The independent `qualify_ties` probe checks exact rows for untied documents and
membership in the source's maximal-timestamp candidate set for tied documents;
it reports different baseline picks without treating a valid candidate as an
error. A permanent tie policy remains pending.

Seven gap probes persist independent receipts in the same results table.
The FORMAT probe also retrieves the original tagged YYYY-MM failure from
system.query.history. Replacement is scoped to the label/object/rung; the
baseline and migration_control are never written.
