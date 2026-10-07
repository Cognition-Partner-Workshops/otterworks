# 02 — Data profile: coverage check and gaps (plan step `s2.5-data-profile`)

Run branch `tp-run/mongodb-20261007T161014Z` @ 8ac32f2b, plugin `mongo-migration-plugin` @
`353280fc837193a40ccc005cb62fb4ffaf8ac16f` (`skills/schema-modeling/data_profile.py`, unpatched). Source: the
`mmprt` mini fixture (same database as the live source, see `fixtures/mmprt-mini.json`).

```
data_profile.py --census .migration/census.json --family oracle --source-dsn-secret MMP_RT_SRC_DSN \
  --schema OW_BILLING --allow-full-scan --statement-timeout 300 --out .migration/data_profile.json
→ data profile written to .migration/data_profile.json: stats=173 ok=173   (exit 0)
```

`.migration/data_profile.json`: `profile_version 1`, `origin live`, `census_sha256
af73f0b7…1219` (= the merged `census.json`), 173 stats — **173 `ok`, 0 `skipped`, 0 `failed`, 0 sampled**
(`--allow-full-scan`; every table < 2,000 rows). By query: value_domain 46, code_resolve 34 (+ folded
code_distinct), row_bytes 20, text_shapes 16, fanout 13, fk_integrity 13, embed_bytes 13, pointer_resolve 10,
csv_elements 7, eav_shape 1 (+ folded eav_attrs).

**Codes table:** found by the profiler on its own — subject `codes_table: CODES, type_col: CODE_TYPE, value_col:
CODE_VAL` on all 34 `code_resolve` stats. `--codes-table` was **not** passed.

This document is the ticket's "read the output, don't trust the exit code" check. §1 maps each required item to
what the JSON actually contains; §2 lists what the profiler did not measure (input for `05_decisions.md` §5);
§3 lists data findings surfaced by the stats; §4 is the redaction check. Where a gap was closed by hand it is
marked **manual** — a read-only aggregate query (COUNT / EXISTS / VALIDATE_CONVERSION) run once against the
fixture, not part of `data_profile.json`, no row values retained.

## 1. Required coverage vs what the JSON contains

| ticket item | in `data_profile.json`? | detail |
|---|---|---|
| Fan-out p50/p99/max CUSTOMER_MASTER → INVOICE_HEADER → INVOICE_LINE | **NO** | `fanout` / `embed_bytes` / `fk_integrity` run only over census `relationships` (the 13 FK-backed pairs; `data_profile.py` lines 205–230). The `mmprt` chain is `unenforced_pointer` traps, which get `pointer_resolve` only (resolve rate, no distribution). **manual:** headers per customer over 201 parents min 0 / max 29 / avg 4.98; lines per header over 1,000 parents min 0 / max 6 / avg 1.46. No p50/p99 (gap G1). |
| Fan-out SUBSCRIPTIONS → SUBSCRIPTIONS_HIST | **NO** | Not even a pointer stat: the census `unenforced_pointer` trap on SUBSCRIPTIONS_HIST lists only `TENANT_ID`, `PLAN_ID` — the history key column is named `ID` (not `*_ID`), so the detector did not bind it to SUBSCRIPTIONS. **manual:** 20 subscriptions, hist rows per subscription min 0 / max 1 (6 rows total). Gap G2. |
| Pointer resolution / orphan rate on the planted orphans | yes | `pointer_resolve:INVOICE_LINE.INVOICE_ID->INVOICE_HEADER` non_null 1,500, unresolved **37**, resolve_rate 0.97533 — matches the 37 `orphaned_rows` planted by the seed manifest. `INVOICE_LINE.CUST_ID` and `INVOICE_HEADER.CUST_ID` → CUSTOMER_MASTER resolve 1.0. `SUBSCRIPTIONS_HIST.TENANT_ID/PLAN_ID` resolve 1.0. All 13 FK `fk_integrity` stats: 0 orphans, 0 null FKs. See §3 for the TENANT_ID pointers. |
| EAV shape of ENTITY_ATTR_VALUE (distinct attr keys, values per entity) | partial | `eav:ENTITY_ATTR_VALUE` → distinct_attrs **8**, entities 70, p99/max attrs per entity **1**. But the subject is `entity_cols: ["EAV_ID"]` — the profiler keyed "entity" on the row PK, so attrs-per-entity is trivially 1. **manual** keyed on (ENTITY_TYPE, ENTITY_ID): 58 entities, max 4 attrs per entity; all 70 rows ENTITY_TYPE = CUSTOMER and all 70 ENTITY_ID resolve to CUSTOMER_MASTER.CUST_ID. Gap G3. |
| Text-date conformance for every dirty-date column in CUSTOMER_MASTER | partial | `text_shapes` ran on all 5 trap columns. `SIGNUP_DT`: `%d-%b-%y` 0.845771 (170/201), 18 shape classes incl. `99-XXX-99` ×7, `N/A` ×6, blank-dashes ×6, `99-99-999` ×6, `9/9/9999` ×4, `99-999-99` ×2 → 31 non-conforming. `LAST_ACTIVITY_DT`: `%d-%b-%y` 1.0. `LAST_INVOICE_DT`, `LAST_PAYMENT_DT`, `TERMINATE_DT`: `shapes: [] conformance: {}` with no null count — **manual:** all three are 100 % NULL (0/201). The seed planted **41** dirty dates in SIGNUP_DT; **manual** `VALIDATE_CONVERSION(signup_dt AS DATE,'DD-MON-RR') = 0` → 41. So 10 planted dirty values are shape-conforming but not valid dates: shape conformance ≠ parseability (gap G4). |
| Packed / CSV column shape | partial | `csv_elements` on 7 columns: CUSTOMER_MASTER.RELATED_ACCT_IDS max 4 / avg 2.59, PROMO_CODES_CSV max 2 / avg 1.48, INVOICE_LINE.GL_ACCT_CSV max 3 / avg 2.04; CHILD_ACCT_IDS null/null (**manual:** 0/201 non-null); the 3 CUSTOMER_MASTER_HIST columns null/null (table empty). The 23 planted `malformed_csv_lists` are **not** measured — element counts only, no malformation stat. **manual** (leading/trailing/double delimiter, `;`, or blank): 23 of 160 non-null RELATED_ACCT_IDS. Gap G5. |
| Null / cardinality for `*_CD` columns joined to CODES | yes | `value_domain` (value → count, null_count) on every `*_CD` / `*_YN` trap column (46) and `code_resolve` (34) against CODES(CODE_TYPE, CODE_VAL): per column the candidate CODE_TYPEs whose values overlap, `full_cover` types, and unresolved values/rows. The profiler cannot tell *which* CODE_TYPE a column belongs to — most columns list 4–6 full-cover candidates (e.g. CUST_TYPE_CD is fully covered by CUST_STATUS, CUST_TYPE, NOTIF_KIND, PHONE_TYPE, PLAN_TIER, USAGE_KIND); the binding is a modeling decision (gap G6). Unresolved: §3. |

## 2. Gaps — what the profiler skipped, failed, or did not measure

No stat has `status: skipped` or `failed`. The gaps are features the stat catalogue does not cover or
measures with a weaker proxy:

| id | gap | evidence |
|---|---|---|
| G1 | No fan-out / embed-size distribution for unenforced pointer chains (CUSTOMER_MASTER → INVOICE_HEADER → INVOICE_LINE, INVOICE_LINE → INVOICES alternative) | `fanout`, `embed_bytes` emitted only for census `relationships` (13). 0 of the 10 `pointer_resolve` pairs have a distribution. |
| G2 | SUBSCRIPTIONS → SUBSCRIPTIONS_HIST and CUSTOMER_MASTER → CUSTOMER_MASTER_HIST history links unmeasured | `history_copy` trap has no stat kind; SUBSCRIPTIONS_HIST.`ID` not detected as a pointer. CUSTOMER_MASTER_HIST has 0 rows (UNT8-2 decision). |
| G3 | EAV attrs-per-entity keyed on the row PK (`EAV_ID`) instead of (ENTITY_TYPE, ENTITY_ID) → p99/max = 1 is not the entity shape | `eav:ENTITY_ATTR_VALUE.subject.entity_cols == ["EAV_ID"]`; manual: 58 entities, max 4. |
| G4 | Text-date stats measure shape, not validity; `DATE_FORMATS` has 8 patterns, none with `DD-MON-RR HH24:MI:SS` | SIGNUP_DT 31 non-conforming shapes vs 41 invalid dates; SUBSCRIPTIONS_HIST.HIST_DT single shape `99-OCT-99 99:99:99` with conformance 0.0 on all 8 formats (format simply not in the list). |
| G5 | CSV malformation (empty elements, stray delimiters) unmeasured; delimiter assumed by the profile query | `csv_elements` has only `max_elements` / `avg_elements`; 23 planted malformed lists invisible. |
| G6 | `code_resolve` reports candidate CODE_TYPEs, not a binding; `*_CD` columns with values outside every CODE_TYPE are listed but not classified (new code vs bad data) | SEGMENT_CD, REGION_CD, LINE_TYPE_CD (§3). |
| G7 | `repeating_group` traps (ADDR_LINE×6, MAIL_ADDR_LINE×6, PHONE×4, EMAIL×3, FLAG×20, UDF×40, UDF_AMT×10, UDF_DT×10 on CUSTOMER_MASTER / _HIST) have no slot-utilisation stat | only the `PHONEn_TYPE_CD` members got `value_domain`. manual: PHONE1 201/201, PHONE2 109/201, PHONE3 0, PHONE4 0 non-null. |
| G8 | `polymorphic_pointer` (ENTITY_ATTR_VALUE.ENTITY_TYPE/ENTITY_ID) only gets `value_domain` on ENTITY_TYPE (`CUSTOMER` 70); ENTITY_ID is not resolved per type | manual: 70/70 resolve to CUSTOMER_MASTER.CUST_ID. |
| G9 | All-NULL columns report `shapes: []` / `values: []` / `max_elements: null` without an explicit "all null" marker; `value_domain` gives `null_count`, `text_shapes` and `csv_elements` do not | CUSTOMER_MASTER.LAST_INVOICE_DT, LAST_PAYMENT_DT, TERMINATE_DT, CHILD_ACCT_IDS. |
| G10 | Stats over the empty CUSTOMER_MASTER_HIST (36 of 173) are `ok` with empty values, not `skipped` | `row_bytes:CUSTOMER_MASTER_HIST rows_seen 0`; `pointer_resolve` resolve_rate `null`. |
| G11 | Not in the profiler's scope at all: trigger/sequence/package behaviour, BILLING_AUDIT_LOG and FIXTURE_META content (row_bytes only), INVOICE_LINE.INVOICE_ID `target_alternatives: [INVOICES]` (only INVOICE_HEADER measured), no LOB stats (no LOB columns exist). | census traps / tables. |

## 3. Data findings surfaced by the stats (record; nothing changed)

- **TENANT_ID pointers do not resolve for the `mmprt` rows.** `pointer_resolve:INVOICE_HEADER.TENANT_ID->TENANTS` 0/1,000, `INVOICE_LINE.TENANT_ID->TENANTS` 0/1,500, `CUSTOMER_MASTER.TENANT_ID->TENANTS` 1/201 (resolve_rate 0.004975). **manual:** TENANTS.ID is a 36-char UUID string (15 rows, 15 distinct); INVOICE_HEADER carries 11 distinct TENANT_ID values, CUSTOMER_MASTER 19, none present in TENANTS.ID. The seeder generates tenant UUIDs for the mini namespace that are not rows of TENANTS; the only resolving row is the static-seed customer. For the model this means TENANT_ID on the `mmprt` tables is a label, not a resolvable reference (plan decision input; not reconciled here).
- **Unresolved `*_CD` values** (`code_resolve`): CUSTOMER_MASTER.SEGMENT_CD 9 distinct, 5 values (5–9) in 101 rows outside every CODE_TYPE; CUSTOMER_MASTER.REGION_CD 12 distinct, 7 values (5–12) in 111 rows unresolved; INVOICE_LINE.LINE_TYPE_CD value 9 in 256 rows unresolved (values 1–3 covered). CUSTOMER_MASTER.STATUS_CD value 99 (2 rows) is covered by CUST_STATUS.
- **All-NULL / mostly-NULL columns:** TERRITORY_CD, CHANNEL_CD, RATE_CLASS_CD, PHONE3_TYPE_CD, PHONE4_TYPE_CD 201/201 null; DUNNING_EXEMPT_YN 200/201 null; SUB_STATUS_CD 66/201 null; INVOICE_LINE.POSTED_YN 313/1,500 null.
- **Fan-out (FK-backed, measured):** SUBSCRIPTIONS→PLANS p50 8 / max 9; USAGE_EVENTS→TENANTS p50 1 / p99 24 / max 24 (embed 2,014 B); INVOICE_LINES→INVOICES p50 5 / max 5; everything else max ≤ 3. Row bytes: CUSTOMER_MASTER avg 334 / max 373, INVOICE_LINE avg 268 / max 291, INVOICE_HEADER avg 152; all others < 150 B.
- Planted anomalies accounted for: 37 orphans ✔ (measured), 41 dirty dates (31 by shape, 41 manual), 23 malformed CSV (manual only).

## 4. Redaction / aggregate-only check

- Case-insensitive grep over `data_profile.json` for the credential keyword, the fixture host port and any Mongo URI scheme → 0 hits; no DSN text, no connection string; the source secret is referenced by env-var name only.
- Every string leaf is a stat id, column/table/CODE_TYPE name, sha256, or a `text_shapes` shape class. Shape masking replaces digits with `9` but keeps letters, so alphabetic literals in text-date columns appear verbatim: in this fixture those are month abbreviations, the planted `XXX` token and `N/A`. No identifiers, amounts, names or dates survive.
- `code_resolve.unresolved_values` and `value_domain.values` hold code numbers / Y-N flags with counts (domain values, not row payload).
