# Contract: u-06-invoice-header-bulk (wave 2, batch w2-b03)

Decision-first contract for the XL unit. One PR per unit (branch-topology policy:
no PR stacks), so this contract is the first ordered commit of the unit PR rather
than a separate PR. Mapping version `map-draft-2`, tolerance version `tol-1`,
canonicalization `map-draft-2-canon`. Offline engagement: `source_access=ddl_only`,
`target_access=local`; recon is `--mode fixture --target-class local` only and is
never merge evidence.

## Mapping rows (verbatim from `.migration/03_mapping_spec.json`, collection `invoiceHeader`)

| source | target | bson | rules |
|---|---|---|---|
| INVOICE_HEADER.INVOICE_ID | `_id` | string | key (natural primary key) |
| INVOICE_NO | invoiceNo | string | empty_string_is_null, null_missing_equiv |
| CUST_ID | custId | string | empty_string_is_null, null_missing_equiv |
| TENANT_ID | tenantId | string | empty_string_is_null, null_missing_equiv (plain reference, D: TENANT_ID) |
| INVOICE_DT | invoiceDt | date | date_string_to_date `%d-%b-%y`, null_missing_equiv |
| DUE_DT | dueDt | date | date_string_to_date `%d-%b-%y`, null_missing_equiv |
| STATUS_CD | statusCd | long | null_missing_equiv (numeric kept; label via `codes` INV_STATUS) |
| TOTAL_AMT | totalAmt | decimal | decimal_round, null_missing_equiv |
| BATCH_NO | batchNo | long | null_missing_equiv |
| embed `lines[]` <- INVOICE_LINE (parent_key INVOICE_ID, key LINE_ID -> lineId, 1:N) | | | |
| INVOICE_NO/CUST_ID/CUST_NO/CUST_NAME/TENANT_ID/ITEM_DESC/SERVICE_PERIOD/SRC_SYSTEM | camelCase | string | empty_string_is_null, null_missing_equiv |
| LINE_NO/LINE_TYPE_CD/BATCH_NO | lineNo/lineTypeCd/batchNo | long | null_missing_equiv |
| QTY/UNIT_PRICE/AMOUNT/TAX_AMT | qty/unitPrice/amount/taxAmt | decimal | decimal_round, null_missing_equiv |
| INVOICE_DT | invoiceDt | date | date_string_to_date `%d-%b-%y`, null_missing_equiv |
| POSTED_YN | posted | bool | yn_to_bool, null_missing_equiv |
| GL_ACCT_CSV | glAcct | array | csv_to_array, null_missing_equiv |

`INVOICE_LINE.INVOICE_ID` is not stored inside the element (it is the parent `_id`);
the harness's embed `fields` list does not include it.

## Key strategy

- `_id` = `INVOICE_ID` (VARCHAR2(36), natural PK). Deterministic; a reload converges
  on the same documents. `lines[].lineId` = `LINE_ID` (natural PK of the child).
- `lines` is sorted by (`lineNo`, `lineId`) so a reload is byte-identical. The seed
  cycles `line_no` 1..25 and duplicates `(invoice_id, line_no)` within an invoice
  (19,512 groups in the fixture), so `lineNo` alone is not a key.

## Type contract (target side)

BSON `date` = UTC midnight datetime parsed with `%d-%b-%y` (Python `strptime`, the
spec rule; NOT Oracle `RR`). `decimal` = Decimal128 of the Oracle NUMBER as text
(no rounding at load; recon applies `decimal_round`). `long` = bson Int64.
NULL and `''` are stored as absent (`null_missing_equiv`). Read paths render
Decimal128 via `normalize()` and Int64 via `str()` to match the Oracle facade JSON.

## Quarantine policy (D: unenforced_pointer, invoiceLine)

- `orphan_line`: INVOICE_LINE row whose INVOICE_ID has no INVOICE_HEADER row.
  Fixture: 37 rows (manifest `orphan_lines`). Never embedded, never dropped
  silently; counted per reason in `load.summary.json` (first 100 rows echoed
  with their key).
- `bad_date:<COL>`: unparseable `%d-%b-%y` text; the field is stored absent and
  the row is kept (a header is never dropped for a bad date). Fixture: 0.
- `bad_yn:POSTED_YN`: token outside Y/N/T/F/1/0/TRUE/FALSE/YES/NO; field absent, row
  kept. Fixture: 0 (NULL is absent, not quarantined: 29,942 rows).
- `duplicate_key`: repeated INVOICE_ID / LINE_ID; second occurrence quarantined.
  Fixture: 0.

## Index plan

`{_id: 1}` (implicit). `{batchNo: 1}` for month-end and CUSTBILL scoping
(`WHERE h.batch_no = :batch_no`). `{tenantId: 1}` for the CUSTBILL admin-tenant
clause (`OR h.tenant_id = :admin_tenant_id`). `{"lines.lineId": 1}` for keyed diff
lookups. No unique index on `lines.lineNo` (see key strategy).

## Read paths rewritten

- `GET /api/reports/month-end` (`reports.py`): one `$match {batchNo}` +
  `$lookup codes (codeType='INV_STATUS', codeVal=statusCd)` + `$group` for the status
  rollup; `$unwind lines` + `$group` for the status x line-type rollup. Labels
  `UNKNOWN(<cd>)` when no code row / code not in {1,2,3,9}. Orphan lines are absent
  from `lines`, which reproduces the legacy inner join.
- CUSTBILL extract: `$match {$or:[{batchNo},{tenantId: ADMIN_TENANT_ID}]}` +
  `$lookup customerMaster` (inner-join semantics: no customer -> no record) +
  `record_type` from `totalAmt < 0`, then the existing `sort_rows` / `format_record`.

## Recon contract and known harness gap

The spec has no `child_where`/`target_where` on the `lines` embed, so Tier 1 compares
`COUNT(INVOICE_LINE)=150,000` against embedded cardinality `149,963`: the 37
quarantined orphans surface as an `embed_cardinality` finding of exactly the
quarantine count, and Tiers 2-4 do not run. A spec scoping change is a human
decision (STOP B), so the official gate is expected to report FAIL with
`failure_class=tolerance_ambiguous`. A second, clearly labelled diagnostic run
adds `child_where`/`target_where` to the subset copy only, to exercise Tiers 2-4;
it is not the gate result.

## Coverage gaps declared

- `customerMaster` is owned by another unit; the CUSTBILL Mongo path's `$lookup`
  is unit-tested with a stub and cannot be replayed against the fixture here.
- Oracle `DD-MON-RR` (CUSTBILL) vs `%d-%b-%y` (spec): they diverge for two-digit
  years 50-68. Fixture years are checked in the report.
