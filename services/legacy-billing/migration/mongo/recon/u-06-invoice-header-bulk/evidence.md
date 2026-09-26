# u-06-invoice-header-bulk: recon evidence (wave 2, batch w2-b03)

`live recon: not possible (offline)`. `target_class=local`, `--mode fixture`.
Everything here is rehearsal evidence and **not merge evidence**
(`merge_eligible=false` in both result.json files). Mapping `map-draft-2`,
tolerances `tol-1` (exact), seed 1, source concurrency 1.

## Runs (2 of the 3 permitted full runs used)

| # | mapping | verdict | what it proves |
|---|---|---|---|
| 1 (official gate) | `mapping.invoiceHeader.subset.json` = verbatim subset of `.migration/03_mapping_spec.json` | **FAIL** | T1 `embed_cardinality` rows(INVOICE_LINE)=150000 vs sum(len(lines))=149963. Delta = 37 = `orphan_line` quarantine count. T2-T4 not reached. Files: `result.json`, `recon.summary.md`, `report.md`. |
| 2 (diagnostic, labelled) | `diagnostic-child_where/mapping.invoiceHeader.DIAGNOSTIC.json` = same subset + `child_where`/`target_where` on the `lines` embed | PASS (all 4 tiers) | T1 2/2, T2 2/2, T3 168713 keyed checks (18750 roots + 149963 elements, 0 findings), T4 3/3 parity ops. Harness warning: extra target elements not keyed in this mode (excluded by equal T1 counts). |

The diagnostic mapping is a local copy; `.migration/` was not edited. Scoping the
embed in the spec is a human decision (STOP B), so the reported gate is run 1:
`status=FAIL`, `failure_class=tolerance_ambiguous`.

## Quarantine <-> finding correspondence (collection/field/count level)

| quarantine reason | count | harness finding |
|---|---|---|
| `orphan_line` | 37 | `invoiceHeader` / `lines` / `embed_cardinality` delta 37 |
| `bad_date:*`, `bad_yn:POSTED_YN`, `duplicate_key` | 0 | none |

`load.summary.json` lists all 37 quarantined keys (`line_id`, `invoice_id`).

## Load and idempotency

`load_invoice_header.py`: 18,750 headers, 149,963 embedded lines, 37 quarantined,
indexes `batchNo`, `tenantId`, `lines.lineId`. Two full drop+reload runs hashed
identically (`idempotency.txt`). Recomputed from the target after the second load:
`count_documents=18750`, `sum($size lines)=149963`, `max lines/doc=23`; the only
collection in `ow_billing_migration` is `invoiceHeader`.

## App-level parity (T4, `ops.json`, batch 85559852 = ns `demo`)

- `month_end_by_status_demo`: 3 groups, counts and Decimal sums identical.
- `month_end_by_status_line_type_demo`: 12 groups, counts/amount/tax/invoices_touched identical.
- `custbill_scope_demo`: `TO_DATE(invoice_dt,'DD-MON-RR')` vs stored `%d-%b-%y` date identical;
  probe of two-digit years 50-68 (where RR and %y diverge) = 0 rows in all three date columns.

## PROFILE FEEDBACK (rules derived, not in the profile/mapping)

1. Embed with a quarantined orphan child: the harness has no quarantine-aware exclusion; the
   only lever is `embeds[].child_where` + `target_where` in the mapping, which is a spec change.
2. `child_where` must be spelled with the child alias (`invoice_id IN (SELECT invoice_id FROM invoice_header)`),
   `target_where` is a JSON string (`"{}"` when the target has no extras).
3. `lines[]` ordering: seed duplicates `(invoice_id, line_no)`; sort by `(lineNo, lineId)` for a
   byte-identical reload.
4. Month-end totals: Oracle `FM...0.00` == Python `Decimal.quantize(0.01)` rendered with `format(d, "f")`;
   `UNKNOWN()` for NULL `status_cd` (Oracle `TO_CHAR(NULL)` is empty).
5. `$dateToString` `%b` is not portable; compare dates as BSON dates with `datetime_utc_truncate_ms`.
6. The harness Tier 4 replays `source_sql` on the same single Oracle connection, so one
   `--ops` file per unit is enough within `--source-concurrency 1`.
