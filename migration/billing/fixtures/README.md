# Oracle billing fixture (plan step `s2.4-fixture`)

`demo.json` is the committed "before" contract for the `OW_BILLING` -> Atlas
migration: one deterministic run of the local Oracle Free fixture, joined with
the merged census and the planted anomalies enumerated as sets. Every unit
develops fixture-first against it; the live recon report (not this file) is
merge evidence.

```sh
make oracle-billing-up                       # Oracle Free on localhost:52521/FREEPDB1
make oracle-billing-seed NS=demo             # seed 714559852, batch_no 85559852
uv run --with oracledb==2.5.1 python migration/billing/fixtures/build_fixture.py --ns demo
uv run --with oracledb==2.5.1 python migration/billing/fixtures/build_fixture.py --ns demo --check
```

`build_fixture.py` reads the seed's git-ignored runtime manifest
(`testdata/legacy/manifests/demo.json`), `../census.json` and
`../tolerances.json`, then runs read-only queries (`SET TRANSACTION READ ONLY`)
against the local fixture only; it refuses any host other than localhost and
never reads `OW_TP_ORACLE_RO_DSN`. It aborts if the seed-owned row counts or
the `CUSTOMER_MASTER` / `INVOICE_LINE` checksums it recomputes differ from the
runtime manifest, if an enumerated anomaly set differs in size from what the
seed planted, or if a fixture-vs-census row delta is not accounted for.
`--check` rebuilds in memory and fails if the committed file is stale.

## What is in `demo.json`

| key | content |
|-----|---------|
| `seed` | namespace, seed, batch_no, generator version, per-table ownership predicates, seed-owned rows and checksums (`md5` of `pk:amount\n` in PK order) |
| `census` | sha256 and capture time of `../census.json`, the 20 in-scope tables, tenants by namespace (9 baseline + 60 `demo::`) |
| `tables` | per table: census (live) rows, fixture rows, delta |
| `census_delta` | the fixture-only rows, by PK: the `static_seed_version` 2 set from `04_upgrade_static.sql` (OtterWorks Admin tenant/customer and dependants, 14 rows) that the live host does not have |
| `anomalies[]` | the sets the recon compares with `tolerances.json#planted_anomalies.compare_as == "set"` |
| `legacy_representations` | every `VARCHAR2(9) *_DT` column classified valid / calendar-invalid / malformed / null under DD-MON-YY + Oracle RR, and every `*_YN` CHAR(1) value histogram including NULL |

Anomaly sets (all PK lists are sorted and carry a `set_sha256`):

| kind | target | count | set |
|------|--------|-------|-----|
| `orphaned_rows` | `INVOICE_LINE` | 37 | `line_ids` whose `INVOICE_ID` has no `INVOICE_HEADER` (`INVOICE_NO` = `DEMO-GHOST-*`) |
| `dirty_dates` | `CUSTOMER_MASTER.SIGNUP_DT` | 50 | `cust_ids`; 39 malformed (`N/A`, `1/1/1900`, ...) + 11 well-formed but impossible (`31-FEB-24`, `29-FEB-23`) |
| `malformed_csv_lists` | `CUSTOMER_MASTER.RELATED_ACCT_IDS` | 31 | `cust_ids`; values not matching `^\d{5}(,\d{5}){0,3}$` |
| `eav_boolean_spellings` | `ENTITY_ATTR_VALUE` | 8333 seed rows | `(attr_name, attr_value)` matrix; booleans spelled `Y/N/1/0/TRUE` next to `blue`, `3.14`, `see ticket 48213`; case-variant `tax_region_override` in the static rows |

Row counts of the seed-owned slice (`CUSTOMER_MASTER` 25000, `ENTITY_ATTR_VALUE`
8333, `INVOICE_HEADER` 18750, `INVOICE_LINE` 150000, `demo::` `TENANTS` 60)
equal the census exactly. `TENANTS` is shared across namespaces, so a recon
scoped to `demo` must filter on `name LIKE 'demo::%'`.
