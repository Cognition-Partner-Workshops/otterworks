# Billing parity audit: seed 1110, 20000 rows, 20261109

No Snowflake connection was made for this audit. Historical statements below use
the saved `migration/dw-exit/.runs/windows-close/billing-fixed.json` artifact, not
a new query against the clone. The clone remains untouched.

## PC: what was an adapter artifact?

`warehouse/parity/commands.py::fetch` uppercases column names. Its `parity` function
selects BEFORE columns minus YAML exclusions, checks that AFTER has those names,
then calls `warehouse/parity/compare.py::compare` with the declared business keys
and captured PostgreSQL source types. It does not require the same column order
or reject extra AFTER columns. Numeric scale is normalized; only fixed CHAR
trailing spaces are ignored. String case is not ignored. Billing exclusions are
empty in `warehouse/parity/mappings/sfx_billing.yml`.

The original adapter incorrectly used the BTEQ board's exact column-list check
for PC, so even an extra `SRC_ROW_NO` caused an error. It also compared a clean
DuckDB model build with BTEQ-populated legacy tables. The revised adapter uses
the existing PC comparator, and mirrors `commands.before`: fresh PC bootstrap,
one full billing workflow on the same generated PSV inputs, then capture.
All seven targets start at zero rows. Like a first dbt build on empty targets,
the local SELECTs use `is_incremental() == False`; existing-target incremental
and idempotence behavior is not asserted.

Evidence is saved under `migration/dw-exit/.runs/windows-close-duckdb/`:
`pc-duckdb.json` records input SHA-256s, zero initial target counts, actual column
lists, missing/extra columns, and comparison metrics where computable.
`pc-legacy-workflow.log` shows 7/7 sessions succeeding against the fresh database.

## PC: final causes

These contracts are defined independently by the exported mapping TARGETFIELDs
under `etl/informatica/repository/SFX_BILLING/mappings/` and by
`etl/informatica/tests/fixture/bootstrap.sql`. The checked-in models live under
`warehouse/dbt/models/pc/billing/`.

| Mapping | Before / after | Audited outcome |
|---|---:|---|
| `m_SFX_CUSTOMER_ACCOUNT` | 2100 / 2100 | Real model contract mismatch: emits `ACCOUNT_NO`, not required `ACCOUNT_NUMBER`, and omits `COUNTRY_CD` and `REGION_CD`. |
| `m_SFX_STG_CUSTOMER_ACCOUNT` | 2100 / 2100 | Same three required columns missing; extra `SRC_ROW_NO` is allowed and is not the RED cause. |
| `m_SFX_INVOICE_HDR` | 20100 / 20100 | Real model contract mismatch: emits `INVOICE_NO`, not required `INVOICE_NUMBER`, and omits nine additional legacy fields listed below. |
| `m_SFX_STG_INVOICE_HDR` | 20100 / 20100 | Same ten required columns missing; extra `SRC_ROW_NO` is allowed. |
| `m_SFX_INVOICE_LINE` | 20000 / 20000 | **GREEN.** Its original RED was an adapter artifact: 23134 pre-existing BTEQ rows plus rejection of the extra `SRC_ROW_NO`. Named-column keyed hashes now match. |
| `m_SFX_PAYMENT` | 20000 / 20000 | Real model contract mismatch: required `PAYMENT_REFERENCE` is absent; `SRC_ROW_NO` is an allowed extra, not a replacement. |
| `m_SFX_GL_JOURNAL_LINE` | 56230 / unavailable | Real lookup contract mismatch: the model's `accounts` CTE reads `PC_SRC.GL_ACCOUNT.ACCOUNT_CODE`, but the bootstrap and `harness.setup` seed define `ACCOUNT_NUMBER`. No PSV field or adapter alias can supply an undeclared source column. |

The nine additional missing invoice fields are `TAX_RATE_ID`, `SUBTOTAL_AMOUNT`,
`TAX_AMOUNT`, `INVOICE_PERIOD`, `PERIOD_KEY`, `PRIOR_PERIOD_END_DT`, `INVOICE_MONTH`,
`PERIOD_CLOSED_CD`, and `CURRENCY_CONTROL_TOTAL`.

The original GL baseline's 61914 rows included 5684 pre-existing non-PC rows;
the clean workflow writes 56230 from zero. Its model still fails before producing
an output. The six remaining PC REDs are contract/execution failures, not computed
hash mismatches. Hash is N/A until required columns and outputs exist. This audit
does not establish equivalence of the remaining shared columns or prove that GL
has no further conversion differences beyond its blocking lookup error.

## BTEQ: historical reproduction and GL revision difference

All 20 GREEN/RED statuses and 19 of 20 before/after count pairs match the saved
Snowflake ladder. `TAX_RATE` is GREEN in both. The sole count exception is GL:

* frozen source: 91636 = 8300 October history + 83336 November postings;
* saved Snowflake candidate: 91400 = 8300 history + 83100 current postings;
* restored straight conversion on DuckDB: 83100 current postings only.

The saved GL AFTER profile has minimum ID `202610000000000011` and maximum ID
`202611500000010003`, proving it used period-prefixed IDs and retained history.
That run included the now-reverted uncommitted GL alignment edits. The current
`billing/20_routines.sql` instead unconditionally deletes the entire journal and
generates unprefixed IDs (`invoice_id*10+line_no`); the current load does not insert
seeded GL history. Thus 91400 versus 83100 is a candidate-revision difference,
not an unexplained DuckDB transfer loss. The SQL remains unchanged in this audit.

Frozen source PLAN_CODE columns have PostgreSQL `ci` collation. A diagnostic
forcing binary `COLLATE "C"` joins returns 4025 subscriptions / 20025 eligible
invoices; case-folding those same binary joins returns 4100 / 20084. The converted
RTRIM-only joins are binary on both local DuckDB and the historical Snowflake
run. Hence 75 missing subscription-plan rows and 59 missing invoice postings;
59 times four journal lines accounts for the 236 missing current GL lines.

An additional board snapshot artifact was corrected: unconstrained PostgreSQL
NUMERIC aggregates had defaulted to DECIMAL(38,0), rounding view sums. Source and
saved Snowflake `V_INVOICE_REVENUE` minimum are 947.57; the corrected local source
snapshot now preserves 947.57 rather than 948. This does not make that view GREEN.

These are reproductions of statuses, counts, and demonstrated defect classes,
not a claim of byte-identical backend results. For example, implicit TO_CHAR date
formatting differs between Snowflake session defaults and DuckDB ISO formatting;
the bad period-key arithmetic remains RED on both.

## BTEQ: one-line cause per RED

Each cause is evidenced in the saved/current profiles and samples in
`billing-duckdb.json`; inherited-total differences originate in the unchanged
converted monthly procedure's case-sensitive plan joins.

| Object | Cause |
|---|---|
| `CUSTOMER_ACCOUNT` | Fixed CHAR `STATUS_CD` padding lost on conversion. |
| `PLAN_CATALOG` | Fixed CHAR `PLAN_CODE` padding lost on conversion. |
| `SUBSCRIPTION` | Fixed CHAR `STATUS_CD` padding lost on conversion. |
| `INVOICE_HDR` | Invoice totals diverge after case-sensitive plan joins; converted period-key arithmetic also differs. |
| `INVOICE_LINE` | Case-sensitive plan joins omit 59 generated invoice lines (43134 versus 43075). |
| `PAYMENT` | Fixed CHAR `METHOD_CD` padding lost on conversion. |
| `CREDIT_NOTE` | Fixed CHAR `REASON_CD` padding lost on conversion. |
| `USAGE_DAILY` | Fixed CHAR `USAGE_TYPE` padding lost on conversion. |
| `BILLING_ADJ` | Fixed CHAR `REASON_CD` padding lost on conversion. |
| `GL_ACCOUNT` | Fixed CHAR `ACCOUNT_TYPE` padding lost on conversion. |
| `GL_JOURNAL_LINE` | Restored conversion deletes prior history, drops period-prefixed IDs, and omits 236 current lines through case-sensitive plan joins. |
| `V_ACCOUNT_INVOICES` | Inherits divergent invoice totals. |
| `V_SUBSCRIPTION_PLANS` | Binary plan-code joins omit 75 rows (4100 versus 4025). |
| `V_INVOICE_BASE` | Inherits divergent invoice totals. |
| `V_INVOICE_REVENUE` | Revenue sums inherit divergent invoice totals; source fractional cents are now preserved correctly. |
| `M_SUBSCRIPTION_PLANS` | Binary plan-code joins omit 75 rows. |
| `M_CURRENCY_TOTALS` | Binary currency grouping splits mixed-case USD into extra groups (6 versus 8). |
| `INVOICE_PERIODS` | Epoch-day arithmetic gives period key 19046325 instead of 20261101. |
| `PERIOD_CLOSE` | Prior-month sum inherits invoice differences: 978.67 versus 3454.33 for 17 invoices. |
