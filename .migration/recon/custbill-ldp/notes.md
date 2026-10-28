# custbill-ldp recon notes

## Outcome

`mode=live depth=full`: parity FAIL, merge_eligible=false.
Blocker classes: data, evidence, rerun_policy, structural.

## What converted

`jobs/parse_custbill_fixedwidth.sh` + `jobs/finance_excel_report.pl` ->
Lakeflow Declarative Pipeline `ow_tp_custbill_ldp` (bundle `mig_1793146609`,
serverless, triggered — schedule PAUSED belongs to wave-3's job):

- `parsed_records`: 6-field CBCUST01 parse of `custbill_feed.raw_line`
  (cust_no c1-10, cust_name c11-40, bill_date c41-48 YYYYMMDD->DATE,
  bill_amt c49-60 implied-decimal /100 unsigned, currency c61-63,
  record_type c64-65) + invoice_id/source_file/batch_no/landed_at lineage.
  Four `@dp.expect_or_drop` expectations: len=65, bill_date parses,
  currency in USD/EUR/GBP, record_type in 01/02.
- `quarantine`: the rejected complement of the feed with `reject_reasons`
  array + verbatim raw_line. Empty on this feed (all 18,750 rows valid:
  USD/'01', len 65, dates parse).
- `finance_billing_totals`: month-end rollup (billing_period=last_day
  (bill_date), currency, record_type mapped 01->INVOICE 02->CREDIT else
  UNKNOWN, record_count, total_amount) — the finance_billing_*.csv surface.

## Merge blockers (harness classes)

- `data` / tier_failed — root_count mismatches that are BY CONSTRUCTION, not
  defects: the committed spec maps `quarantine` (0 reject rows) and
  `finance_billing_totals` (204 rollup rows) against the full
  `ow_billing.invoice_header` root (18,750). A rejects-only table and a
  group-by rollup can never equal the root row count; the spec declares no
  scoping (root_where/target_where) or rollup grading for them, and adding
  scope is a plan decision, not a worker's. `parsed_records` matched the
  root count (18,750 = 18,750); tier 3 keyed diffs never ran because tier 1
  gates them.
- `structural` — SDP materializes @dp.table as MATERIALIZED_VIEW: no PK,
  no NOT NULL, and SP grants show as grant_extra vs Oracle. Same class as
  wave-1's forgiven custbill-feed findings (mo-custbill-w1-structural),
  but NO committed merge_overrides entry covers `custbill-ldp` ->
  merge_authority stays `harness`.
- `rerun_policy` / rerun_missing — `dbx-recon shape` cannot read
  materialized views (`_UC_PHYSICAL` filters table_type MANAGED/EXTERNAL
  only), so no fresh/evolved run records could be assembled and
  `--rerun-proof` could not be passed. Harness gap: SDP units can't satisfy
  posture `required` as written.
- `evidence` / routine_parity_missing — dependencies.json declares
  custbill.ow_tp_custbill_ldp writing routines; no committed run proves
  them, carried unproven.

## Fixture

`mode=fixture` ran (no fail-closed abort — no fixture endpoint exists for
OW_BILLING, so nothing was read from a fixture source) and produced the
same FAIL profile. Fixture evidence is never merge evidence; the live run
above is the evidence run. 1 of 3 allowed full runs used.

## Harness workarounds needed (flag for plugin fix)

Same two session-local adapters.py patches as wave-1 (applied per brief):
`t.owner` -> `t.table_owner` in _uc_schema_facts; oauth-m2m
`sql.connect(access_token=_databricks_bearer())`. Plus NEW: `_UC_PHYSICAL`
excludes MATERIALIZED_VIEW — SDP target tables are invisible to `shape`
and partially to tier 0.

## Mapping spec normalization

Committed spec `object` rewritten 3-part -> bare table name (target adapter
prefixes catalog/schema itself). No root_where/target_where added — those
are scope and need a plan decision.

## Deploy

`databricks bundle deploy -t mig_1793146609` -> pipeline ow_tp_custbill_ldp
created; `bundle run` -> update ee05e93e COMPLETED. Tables landed:
parsed_records 18,750, quarantine 0, finance_billing_totals 204.

## Failure classification

`missing_rule` — the committed mapping spec lacks rules to grade
rejects-only and rollup objects against a full-row root.

## Coverage gaps (tp-pre-pr-self-check)

- `make tp-smoke`: offline gates green (portal renderers, selftests); fails at
  api-gateway step — `go` not installed on this VM (env gap, not code).
- Idempotency: single pipeline run only; `dbx-recon rerun-proof` could not be
  assembled (shape cannot read MVs) — reported as rerun_policy blocker.
- Tier 3 keyed diff of parsed_records never executed (tier 1 gate).
