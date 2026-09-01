# Wave 0 — independent reconciliation report (U0)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0.1** · tolerances **v1** · canonicalization **v1**
· target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · secrets by NAME only
(`MONGODB_ATLAS_URI`, `OW_BILLING_FIXTURE_DSN`) · mode **LIVE** on the parent machine's canonical fixtures
(Oracle `localhost:52521/FREEPDB1` user `ow_billing`; manifest `testdata/legacy/manifests/demo.json` sha256
`0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` re-verified) · seed `714559852` · params
`batch_no=85559852 source_ns=demo` · source-load cap 1 honoured (one Oracle connection at a time; gate, loader
and probes run strictly serially). Reviewer converted nothing in this wave and did not read the child's
diagnoses (`u0.recon.json`, `recon_report_u0.py`) before re-running. Fixtures were neither restarted nor
reseeded (`FIXTURE_META.INITIALIZED_AT = 2026-09-01 20:53:10.961888` before and after).

## 0. Wave-close brief (one page)

| Unit | PR / head attested | Load state graded | Gate (LIVE, verbatim) | Probes | Verdict |
|---|---|---|---|---|---|
| **U0** `codes`, `tenants`, `plans` (Oracle `CODES`/`TENANTS`/`PLANS`) | PR #1423, branch `--u0` @ **`892eb88ac0c149ce8e5f67903e9e636aae4f485d`** (not yet merged into the run branch) | **re-loaded by me from this head** (`scripts/tp_mongo/load_u0.py`, 22:49:53→22:49:55 UTC; 32/69/3 inserted) after first gating the pre-existing load | **PASS** T1 3/3 · T2 14/14 · T3 104/104 (full diff; 0 findings, 0 warnings, no embeds → no UNGRADED) — both before and after the reload; `result.json` identical to the child's committed `.migration/recon/U0/result.json` except `generated_at` | **42/42 ok**, 0 flags | **PASS** |
| **Wave 0** | | | | | **PASS** |

- **Nothing to fix, nothing to explain away.** The three reference tables are NOT NULL on every column, have
  no embeds, no `root_where`, and populations 32/69/3 — every doc was value-graded in full by the harness
  *and* independently re-derived here from Oracle `TO_CHAR` text (no float path) with exact BSON-type checks.
- **Idempotency evidence:** re-running the head loader reproduced `tenants` and `plans` byte-identically
  (sha256 of the sorted extended-JSON dump equal before/after); `codes` differs only because the spec keys it
  on `_key` and the loader lets Mongo assign `ObjectId _id` (content equal — 32/32 value diff clean, `_key`
  bijection intact). Loader is drop-and-recreate per collection; no staging residue; other units' collections
  untouched (documents 2000 / document_snapshots 384 / files 10,000).
- **Cross-unit notes for later waves (not U0 defects):** (a) `CUSTOMER_MASTER.TENANT_ID` (25,000 rows, 50
  distinct) resolves to **zero** rows of `TENANTS` in the *source* itself (no FK on `CUSTOMER_MASTER`) — the
  U1 `customers` mapping must not assume `tenant_id → tenants._id` resolves; (b) `CUSTOMER_MASTER.REGION_CD`
  values 1..12 have no `CODES` type (`REGION` absent in source). `SUBSCRIPTIONS.TENANT_ID` (69 distinct) and
  `SUBSCRIPTIONS.PLAN_ID` (3) resolve 100 %; `tenants.status_cd` ⊂ `TENANT_STATUS`, `plans.tier_cd` ⊂
  `PLAN_TIER`, `INVOICE_HEADER.STATUS_CD` ⊂ `INV_STATUS`, `CUSTOMER_MASTER.STATUS_CD` ⊂ `CUST_STATUS`.
- **Grading-only amendments: none warranted.** The v1.0.1 codes key expression (`CODE_TYPE||':'||CODE_VAL`
  → `_key`) is exactly what the loader emits and is unique on 32/32.
- **Cost (U0, serial, parent machine):** gate run 1 3.9 s (3 COUNT + 14 aggregate + 3 full keyed fetches) ·
  reload 2.7 s (3 SELECTs) · gate run 2 4.2 s · probes 11.2 s (≈60 small Oracle statements incl. two PL/SQL
  calls, one connection) · unit tests 0.1 s. Total ≈ 22 s of source time, all under the cap of 1.
- **Recommendation:** merge PR #1423 at `892eb88a` into the run branch; record this head as the attested SHA.

---

## 1. Gate invocation (verbatim harness, plugin `mongo-migration-plugin-6d021e15/0.2.1`)

```
recon selftest                      # PASS: 9 canonicalization rules exercised
recon run --unit U0 --family oracle \
  --mapping <U0 subset of .migration/03_mapping_spec.json>   # see note
  --tolerances .migration/02_tolerances.json \
  --canonicalization .migration/canonicalization.json --mode live \
  --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGODB_ATLAS_URI \
  --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo \
  --out wave0_evidence/U0/gate_run1   # pre-existing load
  --out wave0_evidence/U0/gate        # after reload from head 892eb88a (authoritative)
```

Mapping note: the harness iterates every collection in the file it is given, so the unit gate has to be
fed the unit's collections. I generated `wave0_evidence/U0/mapping_u0_subset.json` **mechanically** from
`.migration/03_mapping_spec.json` at the head (all top-level keys retained, `collections` filtered to
`unit == "U0"`). It is byte-for-byte the same as the child's `.migration/recon/U0/mapping/u0.json` except
that the child's file carries one extra informational key `projection_note` (ignored by the harness).
Input hashes at head `892eb88a` (identical on the run branch `2b23785c`): `03_mapping_spec.json`
`57de55f2…7bb45`, `02_tolerances.json` `d67ccdda…4ada7`, `canonicalization.json` `527cf87c…3eb9`.

Result (both runs): `PASS` — Tier 1 `counts_through_mapping` 3 checks; Tier 2 `per_field_aggregates` 14
checks (8 string fields deferred to Tier 3 as designed); Tier 3 `keyed_diffs` 104 checks, `full_diff` mode,
populations codes 32 / tenants 69 / plans 3; warnings `[]`. Tier 4 not applicable (no recorded ops file for a
reference-data unit) — app-level parity replayed by hand in §3.9.

Source pre-check / drift triage (read-only, twice): `CODES`=32, `TENANTS`=69, `PLANS`=3 on both passes;
`FIXTURE_META` unchanged → no drift, no defect. Excluded object `FIXTURE_META` is not in the target.

## 2. Load state and head attestation

- Branch `tp-run/mongodb-20260901T205236Z--u0` head = `892eb88ac0c149ce8e5f67903e9e636aae4f485d`
  (`git ls-remote`, re-checked after the run). Not an ancestor of the run branch (PR #1423 open).
- The child's committed load (`load_report.json`, 21:25:01Z) predates the head commit (22:25:48Z) although
  `scripts/tp_mongo/load_u0.py` last changed in `b14d3618` (21:27) and is unchanged at head (sha256
  `5bda45e9…f320`). Per the wave brief I nevertheless re-ran the loader from the head into the target and
  graded *that* state; the pre-reload gate is kept as `gate_run1/` for completeness (identical result).
- Loader read (before running): drop + create per collection, `insert_many(ordered=True)`, unique index
  `(code_type, code_val)` on `codes` only, target-db guard, secrets by name, `ROUND_HALF_EVEN` quantize for
  `NUMBER(12,2)/(12,6)`, `Int64` for `NUMBER(10,0)`, `rstrip(" ")` for `CHAR`, `""→None`. Read-only on Oracle.
- Unit tests at head: `python -m pytest scripts/tp_mongo/tests` → 16 passed (7 are U0's).

## 3. Adversarial probes (beyond the gate) — 42/42 ok (`wave0_evidence/U0/probes.json`, `probe_u0.py`)

| # | Probe | Result |
|---|---|---|
| 3.1 | Independent full value diff, expected docs re-derived from Oracle `TO_CHAR` text through the spec (codes 32, tenants 69, plans 3) | ok — 0 diffs, 0 missing, 0 extra |
| 3.2 | BSON type per field exactly as spec: `int` (int32) for `NUMBER(4,0)`, `long` for `INCLUDED_UNITS`, `decimal` for fees/rates, `string` elsewhere | ok |
| 3.3 | Field-set audit — no undeclared fields (spec fields + `ns`; `codes` additionally the auto `ObjectId _id`) | ok |
| 3.4 | Doc-level check of aggregate-only fields: `Decimal128` text == Oracle text (`49.00/0.055000`, `149.00/0.035000`, `499.00/0.020000`); `SUM/MIN/MAX(code_val)` 389/1/99 both sides | ok |
| 3.5 | Null / missing / empty-string distribution per field, all 14 fields: source NULL+blank == target null+missing, and no `""` in target | ok — all zeros (every column NOT NULL) |
| 3.6 | Duplicate keys: `codes._key`, `(code_type, code_val)`, `tenants.name` (UQ), `plans.code` (UQ); `_id == id` on tenants/plans; `_key == code_type:code_val` on 32/32 | ok — none |
| 3.7 | Min/max boundary docs for every field (14 fields × MIN/MAX incl. `LENGTH()` extremes) — full-field compare | ok — 28/28 equal |
| 3.8 | Key extremes under BINARY (Oracle) vs simple binary (Mongo) collation identical for all three keys | ok |
| 3.9 | `CHAR(1)` padding: 0 padded values in source (so `rstrip_spaces` is a no-op here), 0 whitespace in target; VARCHAR2 lead/trail whitespace counts 0 == 0 | ok |
| 3.10 | Value distributions: `tax_exempt_yn` N 63 / Y 6; `status_cd` 10:68 / 20:1; per-`code_type` cardinality (10 types) | ok — identical |
| 3.11 | `ns == "mongo_205236"` on 100 % of U0 docs | ok |
| 3.12 | Indexes exactly as spec: `codes` `_id_` + unique `code_type_1_code_val_1`; `tenants`/`plans` `_id_` only | ok |
| 3.13 | Quarantine classes compared as SETS: U0 declares none → expected 0; quarantine db holds only `orphan_document_snapshots` (U3) | ok |
| 3.14 | Empty-collection behaviour: loader with 0 rows creates the collection + index and inserts nothing (no empty `insert_many`), reports 0/0 | ok (exercised on a fake DB; no empty source table exists) |
| 3.15 | Embed-array length distribution vs child rows | n/a — U0 has no embeds (nothing UNGRADED) |
| 3.16 | No loader residue; other units' collections untouched by the reload | ok |
| 3.17 | Manifest sanity: `oracle.OW_BILLING.TENANTS rows=60` = demo-seeded tenants; table has 69 = 60 `demo::tenant-*` + 9 base-schema rows; `root_where` is `null` so all 69 are in scope and all 69 are in the target | ok (explained, not drift) |
| 3.18 | Cross-unit shared references (see §4) | ok / noted |
| 3.19 | App replay `PKG_OW_UTIL.F_CODE_DESC(type,val)` for all 32 codes + `('INV_STATUS',9999)`, `('NOPE',1)`, `('INV_STATUS',NULL)` vs Mongo lookup on the unique index with the `UNKNOWN(n)` / `UNKNOWN(-1)` fallback | ok — 35/35 equal |
| 3.20 | App replay `PKG_PLANS.FN_LIST_PLANS` (active plans, `DECODE` tier, `ORDER BY monthly_fee, code`) vs `$match active_yn:"Y"` + `$sort` + read-time tier decode | ok — 3 rows identical |
| 3.21 | App replay RPT-114 status decode (`INV_STATUS` outer join for every `INVOICE_HEADER.status_cd` in batch 85559852 → issued/paid/overdue) | ok |
| 3.22 | App replay tenant lookup by `_id` and by unique `name`, 10 seeded-random tenants | ok |
| 3.23 | Inactive-plan filter parity `NVL(active_yn,'N')<>'Y'` | ok — 0 == 0 |
| 3.24 | Drift triage: source counted twice + `FIXTURE_META` timestamp | ok — stable |

## 4. Cross-unit consistency on shared references (codes / tenants / plans)

| Reference | Result |
|---|---|
| `tenants.status_cd` → `codes[TENANT_STATUS]` | {10, 20} ⊂ {10, 20} ✔ |
| `plans.tier_cd` → `codes[PLAN_TIER]` | {1,2,3} ⊂ {1,2,3} ✔ (matches `fn_list_plans` DECODE) |
| `SUBSCRIPTIONS.TENANT_ID` → `tenants._id` | 69/69 distinct resolve ✔ |
| `SUBSCRIPTIONS.PLAN_ID` → `plans._id` | 3/3 resolve ✔ |
| `INVOICE_HEADER.STATUS_CD` (batch 85559852) → `codes[INV_STATUS]` | {20,30,40} resolve ✔ (RPT-114 join) |
| `CUSTOMER_MASTER.STATUS_CD` → `codes[CUST_STATUS]` | {1,2,3,99} resolve ✔ |
| `CUSTOMER_MASTER.TENANT_ID` → `tenants._id` | **0/50 distinct resolve — in the SOURCE too** (no FK; 25,000 rows). Source property, not a U0 load defect; flagged for U1 (`customers`) mapping/quarantine design. |
| `CUSTOMER_MASTER.REGION_CD` → `codes[REGION]` | no `REGION` code type exists in `CODES` (source). Informational for U1. |
| U3/U4 collections | carry no fields referencing codes/tenants/plans; `ns` consistent (`mongo_205236`) across all six target collections. |

## 5. Findings

1. **No defects.** U0 is a clean reference-data load; gate and 42 independent probes agree.
2. `codes._id` is an auto `ObjectId` while the comparison key is `_key` (spec-conformant: the spec declares
   `key.target = "_key"` and only the `(code_type, code_val)` unique index). Consequence: reloads are not
   byte-identical for `codes` (only `_id` churns). Not a grading matter; worth remembering for any future
   "byte-identical reload" idempotency check.
3. `TENANTS` = 69 vs manifest 60: the manifest counts only demo-seeded tenants; 9 base-schema tenants
   (`Tenant One..Nine`) are legitimately in scope (`root_where: null`). Explained; no amendment needed.
4. Cross-unit: `CUSTOMER_MASTER.TENANT_ID` never resolves to `TENANTS` in the source (§4). Recommend the
   orchestrator carry this into the U1 brief so the `customers` unit does not treat it as a load defect or
   silently drop rows.

## 6. Grading-only amendments

**None warranted.** (v1.0.1 codes key expression verified consistent on 32/32; no tolerance or
canonicalization rule was found missing — `rstrip_spaces`/`empty_string_is_null` have no live cases in U0
data but are harmless.)

## 7. Per-unit cost line

| Unit | Source statements | Wall time | Notes |
|---|---|---|---|
| U0 | gate ×2: 2×(3 COUNT + 14 agg pairs + 3 keyed SELECT); loader: 3 SELECT; probes: ≈60 small SELECT/COUNT + 2 PL/SQL calls | gate 3.9 s + 4.2 s · reload 2.7 s · probes 11.2 s · tests 0.1 s ≈ 22 s | single Oracle connection at a time; no fixture restart/reseed; target writes limited to U0's three collections (drop+recreate by the head loader) |

Evidence: `wave0_evidence/U0/{gate,gate_run1}/{result.json,report.md,recon.summary.md}`, `gate*.log`,
`load_head.log`, `load_report.recon.json`, `mapping_u0_subset.json`, `pre_target_*.sha256`,
`probe_u0.py`, `probes.json`, `probes.log`, `unit_tests.log`.
