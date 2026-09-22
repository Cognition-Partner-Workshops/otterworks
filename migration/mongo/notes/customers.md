# Unit notes: customers (w1-b02)

> Branch: `migrate/billing/w1-customers-r2`. The name
> `migrate/billing/w1-customers` collided with an older, divergent remote
> branch (Sep-18 effort, different layout); the push was rejected
> non-fast-forward and this unit was renamed rather than overwritten.

Collections: `customers` (embeds ENTITY_ATTR_VALUE WHERE
ENTITY_TYPE='CUSTOMER' as `attributes[]`, keyed eavId),
`customerVersions` (CUSTOMER_MASTER_HIST, histDt parsed from
'DD-MON-YY HH24:MI:SS'), `entityAttrValue` (scoped remainder:
`root_where NOT (ENTITY_TYPE = 'CUSTOMER')`,
`target_where {"entityType":{"$ne":"CUSTOMER"}}`).

## Scoped-collection convergence

`entityAttrValue` loads only non-CUSTOMER rows. The loader's delete pass is
scoped by `target_where`, so CUSTOMER-shaped docs can never exist in that
collection and untouched out-of-scope docs would not be swept anyway.

## What the fixture does NOT plant (recon-unsafe traps)

The wave brief lists unparseable dates and malformed CSVs among the seed
traps. Under map-draft-3's canonicalization (`date_string_to_date` default
`unparseable: keep`; `csv_to_array` splits and drops empties) the SOURCE side
keeps a raw value the loader deliberately omits, so any such row is a
legitimate Tier-3 field_diff FAIL, not a quarantine-to-green case. Baseline
seeded data stays reconcilable; the quarantine path is exercised on the
fault leg instead (orphan CUSTOMER EAV -> loader orphan-quarantine +
Tier-1 embed count FAIL).

## Fault injection (this unit's designated fault)

`seed_customers.py --inject-orphan-eav` inserts one CUSTOMER-type EAV row
with an unmatched ENTITY_ID. Recon FAILs: Tier 1 counts the extra child row
against `child_where`. `--remove-orphan-eav` removes it; reload -> PASS.

## Traps seeded

200 customers: sparse columns (every column group populated and sparse),
`*_yn` cycling Y/N/NULL, `*_dt` text dates DD-MON-YY incl. NULL (missing),
well-formed `*_ids`/`*_csv` incl. NULL/single-item, FLAG_01..20 CHAR(1),
UDF_* repeating groups flat, amount edges, `status_cd`/`phone*_type_cd`
values outside CODES. 60 hist rows (2+/changed customer for the first 30,
plus sparse rows). 600 EAV rows: 550 CUSTOMER with matching ENTITY_ID, 50
PLAN/TENANT/INVOICE incl. unmatched ENTITY_IDs (load to entityAttrValue,
no parent needed).

## Seeder idempotency vs trg_customer_master_hist

`trg_customer_master_hist` (02_horror.sql:358) copies each UPDATEd/DELETEd
customer_master row into CUSTOMER_MASTER_HIST. The seed cleanup order is
EAV -> CUSTOMER_MASTER -> CUSTOMER_MASTER_HIST so trigger-written DEL copies
are removed after the customer delete; the hist cleanup also matches the
seeded hist_id band (`hist_id >= 9100000`) because sparse seed rows have a
NULL cust_id that LIKE cannot match. Verified: two consecutive runs both
report CUSTOMER_MASTER_HIST = 60 (previously it grew on every rerun).

## Full convergence on entityAttrValue

The loader passes `full_converge={"entityAttrValue"}`: per map-draft-3 D-013 this unit is the only writer of that collection, so the whole target converges and a CUSTOMER-type doc stranded by an earlier unscoped load is deleted rather than surviving out-of-scope.
