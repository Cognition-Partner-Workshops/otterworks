---
name: odl-source-mapping
description: How the ODL customer and account data in Db2 (ODL.CUSTMAST/ACCTHIST), Oracle (ACCOUNTS/PRODUCTS) and PostgreSQL (crm.*) maps onto one MongoDB customer document on the t-odl tenant. Covers connecting to the four stores, the profiled source facts, the document shape, the per-source field mapping, key normalization, the cross-source match rule and the source owner's decisions on the conflicts (C1–C4). Invoke before writing ODL sync code, a read API over odl.customers, or any change to the ODL sources.
---

# ODL source mapping (Db2 + Oracle + PostgreSQL → MongoDB `odl.customers`)

Applies to the `demo-odl` branch and tenant `t-odl` (namespace `otterworks-odl`), seed
`ODL_SEED=1795112287` with the default sizes in `services/odl-sources/SEED-SPEC.md`.
Every count below was measured on the live tenant, not derived from the generator.
If the seed or sizes change, re-run the profile (section 2) before trusting a number.

## 1. Connecting from the VM

The sources and MongoDB are ClusterIP only. With the org AWS key bound in the shell:

- `aws eks update-kubeconfig --name otterworks-dev`. The VM's apt `aws` 1.22 writes
  `client.authentication.k8s.io/v1alpha1`, which current kubectl rejects; `pip install -U awscli`
  first (or edit the kubeconfig to `v1beta1`). kubectl is not preinstalled: download it.
- `kubectl -n otterworks-odl port-forward svc/oracle 1521`, `svc/db2-archive 50000`,
  `svc/operational-data-layer-mongo 27017`.
- PostgreSQL is the shared RDS (`odl-postgres` Secret: host, port, db `otterworks_odl`), not
  reachable from the VM. Start a throwaway forwarder pod in the namespace
  (`alpine/socat tcp-listen:5432,fork tcp-connect:<DB_HOST>:<DB_PORT>`, label
  `run_token=odl-1795112287`, small requests/limits to satisfy the LimitRange), port-forward
  it, and delete it when done.
- Credentials come from Secrets `db2-archive-credentials` (DB2_USER/DB2_PASSWORD, database
  `ODL`), `odl-oracle` (ORACLE_USER `ODL`, service `FREEPDB1`), `odl-postgres` and
  `operational-data-layer-mongo` (root-*/username/password; app user `odl_app`, readWrite on
  `odl`). Read them into environment variables; never print them or put them on argv.
- Python clients that work: `ibm_db` (`ibm_db_dbi`), `oracledb` (thin), `psycopg[binary]`,
  `pymongo`. Select Db2 `FULL_NAME` as `HEX(FULL_NAME)` and decode it yourself (rule K3).

## 2. Profiled source facts

All business columns are NOT NULL; measured null rate is 0% for every column below.
`seed_version` in all three sources is `60424ea3…b3fe` (same configuration fingerprint).

| Source table | Rows | Key / format | Value ranges and notes |
| --- | ---: | --- | --- |
| Db2 `ODL.CUSTMAST` | 50,000 | `CUST_NO` CHAR(10), `C0000001`–`C0050000` + two trailing blanks on all rows (`HEX` ends `2020`) | `FULL_NAME` VARCHAR FOR BIT DATA: 49,500 UTF-8, 500 cp037 (`José García NNNNNN`, every index divisible by 100), 14–20 chars; `ADDRESS` 22–26 chars, 49,319 distinct (not unique); `OPENED_ON` 2010-01-02…2020-12-13 plus 500 sentinel `0001-01-01`; `OPENED_YMD` DECIMAL(8,0) equals `OPENED_ON` as YYYYMMDD on every row (sentinel `10101`) |
| Db2 `ODL.ACCTHIST` | 400,000 | `HISTORY_ID` 1–400,000; `CUST_NO` same padded CHAR(10) | exactly 8 rows per customer, no orphans; `EVENT_ON` 2020-01-01…2023-12-30, no sentinels; `AMOUNT` DECIMAL(15,2) 0.07…9,999.98, none ≤ 0 |
| Oracle `ACCOUNTS` | 40,000 | `ACCOUNT_ID` NUMBER(15) 7,000,000…7,679,983 step 17 | `HOLDER_NAME` 39,400 `First Last NNNNNN`, 600 `Last, F. NNNNNN`; `ADDRESS` 39,572 distinct; `PRODUCT_ID` 1–4, 10,000 each (nullable in DDL, 0 nulls); `BALANCE` NUMBER(15,2) 6.77…999,998.15; `OPENED_AT` DATE, New York wall clock, 2024-01-01…2024-11-03, all `14:35:20` except IDs 7000000/7000017 (2024-03-10 01:55, 03:05) and 7000034/7000051 (2024-11-03 01:15, 01:45) |
| Oracle `PRODUCTS` | 4 | `PRODUCT_ID` 1–4 | Everyday, Savings, Business, Premium |
| PG `crm.contacts` | 30,000 | `contact_id` UUID v5, lowercase | `credit` DOUBLE PRECISION 0.01…99.99; 600 rows render `0.30000000000000004` (every 50th); names/addresses all `First Last NNNNNN` / Cedar Road |
| PG `crm.service_cases` | 60,000 | `case_id` UUID | exactly 2 per contact; one subject (`Account statement request`); `opened_at` TIMESTAMP without zone, all `2024-11-04 09:30:00`; no index on `contact_id` (seq scan) |
| PG `crm.subscription_snapshots` | 30,000 | `contact_id` UUID (PK, FK) | one per contact; `status` = `active` on all rows |
| MongoDB `odl` | 0 collections | — | only the `odl_app` user exists; the sync must create the collection and indexes |

PostgreSQL server `TimeZone` is `UTC`; Oracle `DBTIMEZONE`/session report `+00:00` even
though the loader writes New York wall clock (DATE stores no zone, so the session setting
says nothing about the values).

## 3. Document shape

One document per golden customer in collection `odl.customers` (option 1 of the target
README: golden record with embedded source records and provenance). Source rows are small
and bounded (1 account, 8 history rows, 2 cases per person), so they are embedded.

```json
{
  "_id": "cus_3b0c…",                      // K6
  "schema_version": 1,
  "match_key": "sha256(name_norm|address_norm)",
  "name": "José García 000600",
  "address": "1010 Cedar Road, Suite 0",
  "customer_since": "2011-08-24",           // date string or null (C4)
  "source_keys": {
    "db2_cust_no": "C0000601",              // or null
    "oracle_account_ids": [7010200],        // [] when absent
    "crm_contact_id": "04d0d3da-3138-5a37-9d01-0cc2202ddf6c"  // or null
  },
  "source_records": {
    "db2": {"cust_no": "C0000601", "opened_on": "0001-01-01", "opened_ymd": 10101}  // raw values, kept as stored (C4)
  },
  "accounts": [{
    "account_id": 7010200, "product": {"id": 1, "name": "Everyday"},
    "balance": {"$numberDecimal": "123456.78"},
    "opened_at": {"$date": "2024-01-xxT19:35:20Z"},
    "opened_at_local": "2024-01-xxT14:35:20", "opened_at_tz": "America/New_York"
  }],
  "account_history": [
    {"history_id": 601, "event_on": "2021-08-23", "amount": {"$numberDecimal": "42.17"}}
  ],
  "crm": {
    "contact_id": "04d0d3da-…", "credit": {"$numberDecimal": "0.30"},
    "subscription_status": "active",
    "service_cases": [{"case_id": "…", "subject": "Account statement request",
                       "opened_at": {"$date": "2024-11-04T09:30:00Z"}}]   // read as UTC (C3)
  },
  "match": {"rule": "exact-name-address", "sources": ["db2", "oracle", "postgres"],
            "status": "matched"},       // matched | single-source
  "exception_ids": [],                   // references into odl.mapping_exceptions
  "provenance": {"name": ["db2", "oracle", "postgres"], "address": ["db2", "oracle", "postgres"],
                 "customer_since": "db2"}
}
```

Indexes: unique `match_key`; unique partial on `source_keys.db2_cust_no` and
`source_keys.crm_contact_id` (where not null); unique multikey on
`source_keys.oracle_account_ids`; `match.status`.

Exceptions for human review live in collection `odl.mapping_exceptions`, one document per
exception, referenced from each affected customer's `exception_ids`:

```json
{
  "_id": "exc_<uuid5(NAMESPACE_URL, 'otterworks:odl:exception:' + reason + ':' + sorted source keys)>",
  "reason": "candidate_match_unconfirmed",   // or ambiguous_local_time
  "customer_ids": ["cus_…", "cus_…"],
  "source_keys": ["db2:C0000002", "oracle:7000017"],
  "detail": {"agreement": "suffix+surname+initial", "db2_address": "…", "oracle_address": "…"},
  "status": "open"                            // a person changes it after review
}
```
Money is always Decimal128 (never double). Dates without a time are `YYYY-MM-DD` strings.

## 4. Field mapping per source

| Target field | Db2 | Oracle | PostgreSQL |
| --- | --- | --- | --- |
| `name` | `FULL_NAME` decoded (K3) | `HOLDER_NAME` | `contacts.full_name` |
| `address` | `ADDRESS` | `ADDRESS` | `contacts.address` |
| `customer_since` | `OPENED_ON`; `0001-01-01` → null (K4, C4); `OPENED_YMD` only as a cross-check | never used as a fallback (C4) | — |
| `source_records.db2` | `RTRIM(CUST_NO)`, `OPENED_ON`, `OPENED_YMD` exactly as stored, sentinel included (C4) | — | — |
| `source_keys.*` | `RTRIM(CUST_NO)` | `ACCOUNT_ID` as int64 | `contact_id` lowercase text |
| `accounts[]` | — | one entry per `ACCOUNTS` row; `product` joined from `PRODUCTS`; `balance` NUMBER → Decimal128 exact; `opened_at` per K5 | — |
| `account_history[]` | `ACCTHIST` by `RTRIM(CUST_NO)`; `AMOUNT` → Decimal128; `EVENT_ON` → date string | — | — |
| `crm.credit` | — | — | `credit` rounded half-even to 2 dp → Decimal128 (K7) |
| `crm.subscription_status` | — | — | `subscription_snapshots.status` (renamed exactly as billing-service maps SQL `status` → REST `subscription_status`) |
| `crm.service_cases[]` | — | — | `service_cases` by `contact_id`; `opened_at` TIMESTAMP read as UTC, the CRM server `TimeZone` (C3) |

Precedence for `name`, `address`: for every auto-matched customer the values are
equal by construction of the match rule, so there is nothing to choose; `provenance`
lists every agreeing source. The 600 C1 pairs are never merged, so no precedence applies.

## 5. Key normalization rules

- **K1 Db2 key:** `RTRIM(CUST_NO)`; never compare padded CHAR(10) to an unpadded literal
  from another engine. History joins use the same trimmed key.
- **K2 Oracle key:** `ACCOUNT_ID` as an integer (int64), no zero padding, no prefix.
- **K3 Db2 name bytes:** select `HEX(FULL_NAME)`; decode strict UTF-8, and if that raises,
  decode cp037. Naive UTF-8 with replacement corrupts 500 names and silently drops 394
  Db2↔Oracle and 300 Db2↔CRM matches (`José García`).
- **K4 Db2 dates:** `0001-01-01` / `10101` is "unknown" → null; it is never a real date.
- **K5 Oracle DATE:** interpret as `America/New_York` wall clock, store UTC `opened_at` plus
  `opened_at_local` and `opened_at_tz`. Spring-gap neighbours are unambiguous
  (01:55 EST → 06:55Z, 03:05 EDT → 07:05Z). The two repeated autumn 01:xx values take the
  first occurrence, EDT/UTC-4 (01:15 → 05:15Z, 01:45 → 05:45Z), and are flagged (C2).
- **K6 Golden id:** `cus_` + `uuid5(NAMESPACE_URL, "otterworks:odl:customer:" + anchor)`,
  anchor = first present of `db2:<cust_no>`, `oracle:<account_id>`, `postgres:<contact_id>`.
  Deterministic across rebuilds; never a random UUID or an ObjectId.
- **K7 CRM credit:** DOUBLE → Decimal128 rounded half-even to 2 dp
  (`0.30000000000000004` → `0.30`; all other values already have ≤ 2 decimals).
- **K8 PG UUIDs:** lowercase canonical text; all 30,000 are valid v5 UUIDs.
- **Text normalization for matching only** (stored values keep source case):
  Unicode NFC, collapse runs of whitespace to one space, trim, `casefold()`.

## 6. Cross-source match rule

No crosswalk or shared key exists in any source. A customer matches across sources when
the **normalized name and normalized address are both exactly equal** (`match_key`).
Name alone or address alone never links (addresses repeat: 49,319 distinct of 50,000 in
Db2, 39,572 of 40,000 in Oracle, 29,753 of 30,000 in CRM). Within each source `match_key` is unique, so the match is 1:1.
Anything that fails the rule becomes its own `single-source` golden document; no fuzzy,
positional or ID-arithmetic linking is applied automatically.

Measured result on t-odl:

| Cohort | Customers | Status |
| --- | ---: | --- |
| Db2 + Oracle + CRM | 30,000 | matched |
| Db2 + Oracle | 9,400 | matched |
| Db2 only (`C0040001`–`C0050000`) | 10,000 | single-source |
| Db2 `C0000001`–`C0000600` ↔ Oracle `7000000`–`7010183` | 600 + 600 | single-source each, 600 exceptions (C1) |
| CRM only | 0 | — |

The 600 review pairs share the 6-digit name suffix but have different addresses (Cedar Road
vs Oak Avenue) and Oracle uses `Last, F.`; 594 agree on surname + first initial, 6 (Db2
`José García` rows C0000001/101/201/301/401/501) agree on nothing but the suffix. Per C1
they are never linked: each side is its own `single-source` customer, and each pair gets one
`candidate_match_unconfirmed` exception.

## 7. Conflict decisions

Decided by source owner, 2026-11-19 (relayed through the PW-Internal service account).
Do not change these in code without a new source-owner decision.

| # | Conflict | Decision |
| --- | --- | --- |
| C1 | 600 Db2↔Oracle candidate pairs (`C0000001`–`C0000600` ↔ `7000000`–`7010183`): same name suffix, different address; 594 also agree on surname + initial, 6 only on the suffix | Never link. Each side is its own customer (1,200 documents). Record each pair once in `odl.mapping_exceptions` with reason `candidate_match_unconfirmed` for later human review. |
| C2 | Oracle 7000034 (`2024-11-03 01:15`) and 7000051 (`01:45`) fall in the repeated DST hour | Read both as the first occurrence, EDT (UTC-4): `05:15Z` and `05:45Z`. Flag each with reason `ambiguous_local_time`. |
| C3 | `crm.service_cases.opened_at` (60,000 rows) is TIMESTAMP without zone | Read it as UTC, the CRM database's server `TimeZone` setting. |
| C4 | 500 Db2 customers with the `0001-01-01` / `10101` sentinel open date | `customer_since` is null in the document; the raw `0001-01-01` and `10101` stay in `source_records.db2`. No fallback to the Oracle account open date. |

Expected exception counts at the default seed: 600 `candidate_match_unconfirmed`,
2 `ambiguous_local_time` (both accounts are also on the Oracle side of C1 pairs, for
C0000003 and C0000004).

If a later decision changes any of these, update this table, the rules above, and the
"Customer source mapping" page in the ENG space of the Confluence mock.
