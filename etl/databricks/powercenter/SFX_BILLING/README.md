# SFX_BILLING PowerCenter → Databricks SQL

## Serverless workflow Job

The Job requires the eight `sfx_` target tables already initialized by `00_ddl.sql`.
It creates no compute: every SQL task uses the existing serverless warehouse supplied
in `DATABRICKS_WAREHOUSE_ID`; deployment rejects a non-serverless warehouse.
With `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, and `DATABRICKS_WAREHOUSE_ID` in the
environment (never committed), run from this directory:

```sh
python3 job.py deploy --output /home/ubuntu/dbx/sfx-job
python3 job.py run --output /home/ubuntu/dbx/sfx-job
python3 job.py run --output /home/ubuntu/dbx/sfx-job
python3 job.py parity --output /home/ubuntu/dbx/sfx-job
```

`deploy` creates one unscheduled Job named `dbx-d1111-sfx-billing-daily` using
Jobs API 2.1, refusing an existing same-name Job. It uploads rendered plain SQL
workspace files to `/Users/<current-user>/dbx-d1111/SFX_BILLING/`, with concrete
`step=job-run` headers. Files are overwritten only inside that run-specific folder.
Job tags are `run_token=dbx-d1111`, `expires=2026-11-24`, `act=scale`; runs inherit
the Job tags. API 2.1 `run-now` has no separate run-tags field, so those values are
also supplied explicitly as run-level Job parameters. No cluster configuration,
email recipients, or credentials are present in the definition.

Each `run` waits for completion before returning and persists its ID immediately.
`max_concurrent_runs=1` and the script's unfinished-run guard prevent overlap.
If interrupted, use `python3 job.py collect --output /home/ubuntu/dbx/sfx-job` to
resume waiting and capture outputs without triggering another run. Job settings,
task states, SQL outputs, and statement IDs are saved in that output directory;
statement IDs are appended to `/home/ubuntu/dbx/statements.tsv` by default.
`parity` uses `step=job-parity`, compares business columns against the PC run-2
references (corrected GL), and fails on missing results or any business difference.
The original GL comparison and identity statistics remain evidence, not assertions:
subsequent Job runs deliberately advance identity beyond the two PC snapshots.

The XML worklet starts both staging sessions independently. CUSTOMER_ACCOUNT
requires STG_CUSTOMER_ACCOUNT success. All three members fail the parent on
failure; both terminal members (CUSTOMER_ACCOUNT and STG_INVOICE_HDR) must succeed
before INVOICE_HDR and INVOICE_LINE. Both must succeed before GL. These gates
flatten the worklet without bypassing either branch.

The XML decision is GL `Status=SUCCEEDED AND TgtFailedRows=0`. SQL GL has no
row-level reject path: any target failure aborts the statement and fails the task.
Thus the `ALL_DONE` condition task tests GL's result state for `success`, which
implies zero target failures under this SQL error model. PAYMENT takes its true
outcome; the false outcome runs a read-only SELECT alert marker. **No email is
sent.** This preserves branching, not PowerCenter's partial-row error recovery.

## Conversion

This conversion is scoped to run `dbx-d1111`, act `scale`, and the seven billing
mappings. Targets use `cpw.dbx_d1111_after.billing__sfx_<table>` because the
`area__table` names are held by a prior act (`act=prove`, `consumer=billing`)
with the baseline contract, not the PC column contract. Do not alter those tables.
Inputs are read only from `cpw.dbx_d1111_before`; target lookups use our `sfx_`
tables. The GL reference lookup reads `before.billing__gl_account`.

## Run

Provide `DATABRICKS_HOST`, `DATABRICKS_TOKEN`, and `DATABRICKS_WAREHOUSE_ID` in the
process environment through the secret manager. No credentials belong in files.
The Python standard library is sufficient. From this directory:

```sh
python3 run.py convert --step convert-run1 --ddl --output /home/ubuntu/dbx/sfx-convert-run1
python3 run.py parity --step parity --run 1 --output /home/ubuntu/dbx/sfx-parity-run1
python3 run.py convert --step convert-run2 --output /home/ubuntu/dbx/sfx-convert-run2
python3 run.py parity --step idempotence --run 2 --output /home/ubuntu/dbx/sfx-parity-run2
python3 -m unittest discover -s . -p test_run.py
```

Use a separate output directory for each invocation: `statements.json` includes
executed SQL, Statement API IDs, status, result schema, and metrics such as
`num_affected_rows`, `num_inserted_rows`, and `num_updated_rows`. `parity.json`
includes count/hash results, samples in both directions, and GL identity metrics.
Every statement ID is also appended to `/home/ubuntu/dbx/statements.tsv`; override
with `--ledger`. No automatic retries or destructive target resets are performed.
SQL templates are split on semicolons, so do not put semicolons in SQL literals.

`PARAMETERS` in `run.py` defines LOAD_DATE, CURRENCY_DEFAULT, and SALES_TAX_RATE
once. The runner substitutes parameters and the required real step into every
statement header. Each created table carries the run-token comment and properties.
DDL uses IF NOT EXISTS; run 2 must **not** drop or recreate the identity table.

## Semantics and evidence

- Flat-file mappings consume the before staging projection already proven equal
  to the seeded landing files (PC positional fields, account_number/account_no
  and invoice_number/invoice_no aliases). Casts to STRING use ISO dates and fixed
  numeric scale. Empty file fields were loaded as NULL in the evidence input.
- STG mappings overwrite. Account/invoice lookups use first-match ROW_NUMBER
  snapshots within the write statement. The checked staging customer keys are
  unique. With duplicate keys absent from the initial lookup, PC can attempt
  multiple inserts; Delta MERGE is not a general emulation of row-by-row PK rejects.
- Invoice VALID and DEFAULT groups are complementary. DEFAULT rows are retained
  with DD_REJECT=3 and load metadata; no default rows occurred in these runs.
  Reject evidence is append-only by load step, unlike the PC file overwritten on
  each session. Query `load_step` when inspecting individual runs.
- Invoice lines and payments MERGE as Update else Insert. Filter conditions use
  coalesce(condition,false); NULL does not pass.
- GL reproduces the date-prefix Pre SQL and three independent UNION ALL router
  groups. The source is STG_INVOICE_HDR, not the filtered final invoice target.
  Unconnected lookup codes 1200/2300/2200 use baseline GL IDs. String concatenation
  coalesces NULL to empty. The postable filter eliminates zero/NULL total amounts;
  TAX_CREDIT additionally excludes zero tax. No GL reject strategy exists in the
  mapping, so no synthetic GL reject table is created.
- PC `_round` and `_to_decimal` use Decimal ROUND_HALF_UP (default Decimal context
  precision 28). SQL uses exact DECIMAL arithmetic, ROUND (HALF_UP, not bround),
  and DECIMAL(14,2) port casts. Equivalence is checked on the seeded domain, not
  asserted for arbitrary overflow or malformed numeric prefixes. CAST failures
  abort a SQL statement rather than reproducing PC's row error/reject recovery.
- GL identity starts at 900001 and increments by 1. Databricks identity values
  are not generally guaranteed gapless or assigned in the PC branch/source row
  order. Compare count/distinct/min/max/span separately and business rows without
  journal_line_id. Do not claim identity-to-business-row correspondence.
- Parity RTRIMs STRING on both sides (CHAR read padding), preserves NULL with
  literal backslash-N, casts dates/numbers canonically, and compares count plus
  summed 60-bit MD5 prefixes. EXCEPT ALL samples in both directions guard against
  hash collisions and preserve multiplicity. The GL original reference is expected
  to fail because its fixture GL IDs differ; the corrected reference is glfix.

Original and corrected PC baselines and the statement ledger are local evidence
under `/home/ubuntu/dbx`, not credentials or generated datasets committed to git.
The full execution report is `/home/ubuntu/dbx/conversion-report.md`.

## Cleanup boundary

Only the three unprefixed tables created by our failed initial attempt were
removed: stg_customer_account, stg_invoice_hdr, invoice_hdr__reject. Version 0
histories at 03:44 matched the exact earlier act=scale CREATE statement IDs;
the staging names had no prior-act versions. No existing prove target was changed
by this continuation. History evidence is `/home/ubuntu/dbx/cleanup-history.json`.
