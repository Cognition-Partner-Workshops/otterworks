# u-02-customers: decision-first contract (batch w1-b02, wave 1)

Mapping `map-draft-2` (`.migration/03_mapping_spec.json`), tolerances `tol-1` (exact:
`numeric_abs_tol=0`, `aggregate_rel_tol=0`), decisions cited from `.migration/05_decisions.json`.
Target namespace: `ow_billing_migration.customerMaster`, `ow_billing_migration.customerMasterHist`
(the only two collections this unit writes; both are dropped and recreated at the start of
every loader run). Offline engagement: `source_access=ddl_only`, `target_class=local`.

## Mapping rows

| Source | Target | Key | Rows (fixture) |
|---|---|---|---|
| `CUSTOMER_MASTER` (154 mapped cols) | `customerMaster` | `CUST_ID -> _id` (natural PK, string uuid) | 25 001 (25 000 seeded + 1 static `OW-ADMIN-0001`) |
| `ENTITY_ATTR_VALUE` where `ENTITY_TYPE='CUSTOMER'` | `customerMaster.attributes[]` `{eavId, entityType, entityId, attrName, attrValue, attrType, createdDt}` | element key `EAV_ID -> eavId`, parent `ENTITY_ID -> _id` | 8 337 (8 333 seeded + 4 static) |
| `CUSTOMER_MASTER_HIST` (157 mapped cols) | `customerMasterHist` | `HIST_ID -> _id` (long) | 0 (trigger-fed; no reader in the repo) |

Field names are the spec's camelCase targets, column-for-column (repeating groups
`ADDR_LINE_1..6`, `FLAG_01..20`, `UDF_*` stay flat per the wave-1 decision). History stays a
separate append-only collection (`history_copy`; never embedded).

## Canonicalization (loader must produce exactly what the harness grades)

- `NUMBER(p,s)` -> `Decimal128`; `NUMBER(p)` -> long; `DATE` -> BSON date (UTC, ms).
- `CHAR(n)` -> rstrip spaces. Oracle `''`/NULL -> field omitted (`null_missing_equiv`).
- `*_YN` -> bool (`Y`->true, `N`->false).
- `RELATED_ACCT_IDS`, `CHILD_ACCT_IDS`, `PROMO_CODES_CSV` -> array: split on `,`, trim,
  drop empty tokens.
- `SIGNUP_DT`, `LAST_ACTIVITY_DT`, `LAST_INVOICE_DT`, `LAST_PAYMENT_DT`, `TERMINATE_DT`,
  `attributes[].createdDt` -> BSON date via `%d-%b-%y`; `HIST_DT` via `%d-%b-%y %H:%M:%S`.

## Quarantine (reason-coded, never dropped, never silently coerced)

| Reason | Rule (05_decisions) | Loader behaviour |
|---|---|---|
| `bad_date` | text date does not parse with its format (`31-FEB-24`, `N/A`, `1/1/1900`, ...) | field omitted; `_quarantine[]` entry `{field, reason, raw}` on the document |
| `malformed_csv` | CSV value contains `;` or the literal token `NULL`/`NONE` | field omitted; `_quarantine[]` entry; value is never split |
| `eav_unexpected_entity_type` | `ENTITY_ATTR_VALUE.ENTITY_TYPE <> 'CUSTOMER'` | counted only; any non-zero count fails the unit (plan gap, not a drop) |

Counts per reason are printed by the loader and reported in the PR.

## Trigger-derived columns (`TRG_CUSTOMER_MASTER_SEQ`)

Loaded rows keep the source values of `CUST_SEQ_NO`, `CUST_NAME_UPPER`, `ROW_VERSION_NO`
verbatim (the trigger already fired in Oracle). For new documents written by the app the
loader module exposes `derive_customer_defaults(doc, next_seq)`: `custSeqNo` from a
sequence when missing, `custNameUpper = upper(custName)`, `rowVersionNo = rowVersionNo or 1`.

## Index plan

- `customerMaster`: `{tenantId: 1, custSeqNo: 1}` (facade `/customer` and `/me`:
  `WHERE tenant_id = :1 ORDER BY cust_seq_no FETCH FIRST 1 ROWS ONLY`).
- `customerMasterHist`: `{custId: 1, histDt: 1}` (audit lookups by customer; no app reader today).
- `attributes[]` is read only with its parent document; no multikey index.

## Code slice

`services/legacy-billing/app/facade.py` `/customer` (lines 121-127, 287-298): replace the two
Oracle queries with `find_one({"tenantId": ...}, sort=[("custSeqNo", 1)])` and return the
embedded `attributes` sorted by `eavId`; 401/404/503 behaviour unchanged.

## Recon

`recon run --mode fixture --target-class local` against the fixture
`.migration/fixtures/ow_billing_demo.json`; live recon: not possible (offline). Local
evidence is rehearsal only and is never merge evidence.
