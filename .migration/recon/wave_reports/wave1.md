# Wave 1 — independent reconciliation report, Part 1 — re-attestation pass (U1, U3, U4)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0** (run-branch `03_mapping_spec.json`) · tolerances **v1**
· canonicalization **v1** · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`)
· secret `MONGODB_ATLAS_URI` (name only) · fixtures: Oracle `localhost:52521/FREEPDB1` user `ow_billing`,
Postgres `localhost:5432/otterworks` schema `otterworks_demo`, LocalStack DynamoDB `localhost:4566` table
`otterworks-file-metadata` · manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`
(re-verified on the parent checkout) · recon params `--seed 714559852 --param batch_no=85559852 --param source_ns=demo`
· source-load cap 1. Session: 2026-09-02 04:19 → 04:35 UTC, parent machine, separate clone `~/wave_recon/`.
This session converted nothing in wave 1 and did not read the children's diagnoses.

## 0. Wave-close brief (one page)

**Wave verdict: PASS (carried).** Every wave-1 unit under review is already **merged into the run branch**,
and each PR branch's *current* head is byte-identical to the head that the prior Part-1 LIVE recon
re-loaded from and gated (`tp-run/mongodb-20260901T205236Z--wave1-recon-part1:.migration/recon/wave_reports/wave1.md`,
commit `475560d4`, 2026-09-02 00:14 UTC — reproduced verbatim below as §1–§6). Per the wave instruction
("units whose PR is already merged into the run branch: attest the merged head and carry the PASS from the
prior wave report for that head"), no unit was re-graded and the LIVE window was not consumed by a gate
re-run; there are **no unmerged units** in this wave (U2 #1432 is outside the scope given for this pass).

| Unit | PR | Current PR-branch head (attested) | Merge commit on run branch | Merged? | Carried verdict (source) |
|---|---|---|---|---|---|
| U1 `customers`, `customers_history`, `counters` (+Q `dirty_signup_dt`, `bad_csv_list`) | #1430 | `c5baa80ab8afd54191b74854ca996fdf133e2c86` | `e87de328` | yes (`merge-base --is-ancestor`) | **PASS** — prior Part-1 LIVE gate @ `c5baa80a`: T1 3/3 · T2 313/313 · T3 33,333/33,333, probes 56/56 (§3.1) |
| U3 `documents`, `document_snapshots` (+Q `orphan_document_snapshots`) | #1420 | `dfa5e9781e08718a7707a0a14ef9e8513149ed92` | `811aed6f` | yes | **PASS** — prior Part-1 LIVE gate @ `dfa5e978`: T1 3/3 · T2 18/18 · T3 16,260/16,260, probes 65/65 (§3.3) |
| U4 `files` | #1419 | `3420f475c29b8889bc8676cebb58a9b4faabff2a` | `cdb0abd4` | yes | **PASS** — prior Part-1 LIVE gate @ `3420f475`: T1 1/1 · T2 12/12 · T3 10,000/10,000 full diff, probes 66/68 (2 explained flags, F-U4-1) (§3.4) |

Head verification (this session, `git fetch origin --prune` at 04:21 UTC): `origin/…--u1` = `c5baa80a`,
`origin/…--u3` = `dfa5e978`, `origin/…--u4` = `3420f475`; each is the second parent of the cited merge
commit and an ancestor of run-branch head `1c03cce7`. Evidence: `wave1_part1_reattest_evidence/attested_heads.json`.

**Cheap state check (no re-grade; ≈3 s of source load, serial):** to confirm the carried PASS still describes
the *current* target/fixture state, this session counted both sides once
(`wave1_part1_reattest_evidence/counts.log`, scripts alongside):

| Population | Source (fixture) | Target (Mongo) | Prior report |
|---|---|---|---|
| `CUSTOMER_MASTER` / `customers` | 25,000 | 25,000 | 25,000 |
| `ENTITY_ATTR_VALUE` (customer) / Σ `customers.attributes[]` | 8,333 | 8,333 | 8,333 |
| `CUSTOMER_MASTER_HIST` / `customers_history` | 0 | 0 (collection exists) | 0 |
| `USER_SEQUENCES` / `counters` | 125000 / 1 / 11001 | 125000 / 1 / 11001 | equal |
| `documents` / `documents` | 2,000 | 2,000 | 2,000 |
| `document_versions` / Σ `documents.versions[]` | 13,876 | 13,876 | 13,876 |
| `document_snapshots` (with parent / orphans) / `document_snapshots` + Q | 390 (384 / 6) | 384 + Q 6 | 384 + 6 |
| DynamoDB items / `files` | 10,000 | 10,000 | 10,000 |
| Quarantine DB classes | — | `dirty_signup_dt` 50, `bad_csv_list` 31, `orphan_document_snapshots` 6, `invoice_feed_orphan_lines` 37 (U2) | 50 / 31 / 6 / 37 |

All equal to the attested state → no evidence of drift or of a post-attestation reload; the carried PASS stands.
(Note for the record: `CUSTOMER_MASTER` carries no `BATCH_NO` column — `batch_no` is a harness param used
by the mapping's `root_where` on other tables; the count above is the whole table, which is the U1 population.)

**Fixtures:** all running (`otterworks-oracle-billing`, `otterworks-postgres`, `otterworks-localstack` healthy,
up 8 h); nothing restarted, reseeded or modified; nothing written to the target.

**Findings (carried, unchanged; still open at these heads):** F-U4-1 (`files.size_bytes` stored int32 vs
declared `long`; value-exact, gate-invisible), F-U3-1 (quarantine-ceiling denominator wording),
F-XU-1 (50 fixture `tenant_id`s absent from `TENANTS` on both sides), F-U1-1 (informational, head moved
during the prior session — final head `c5baa80a` is the one attested here). No new findings.

**Grading-only amendments (recommended, NOT applied):** unchanged from §6 — (a) pin the quarantine-ceiling
denominator; (b) Tier-2 BSON `$type` histogram so declared width is graded. Additionally suggested for the
orchestrator's bookkeeping: (c) when a re-attestation pass finds all units merged and heads unchanged, the
wave report may record a *carried* verdict without spending the LIVE window (as done here) — codify this so
later re-dispatches are not mistaken for missing evidence.

**Per-unit cost (this pass):** U1 0 s source / 1 Mongo count pass; U3 4 pg statements; U4 1 DynamoDB COUNT
scan (10 pages); Oracle 5 statements total (~1 s). Wall clock ≈ 16 min incl. git verification and report;
no loader run, no gate run. Prior Part-1 costs are in §1 below.

---

# Prior Part-1 LIVE report (commit `475560d4`, carried verbatim)

# Wave 1 — independent reconciliation report, Part 1 (U1, U2, U3, U4)

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0.1** · tolerances **v1** · canonicalization **v1**
· target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · `ns = mongo_205236`
· mode **LIVE** on the canonical fixtures (Oracle `localhost:52521/FREEPDB1` schema `ow_billing`,
Postgres `localhost:5432/otterworks` schema `otterworks_demo`, LocalStack DynamoDB `localhost:4566`
table `otterworks-file-metadata`) · manifest `testdata/legacy/manifests/demo.json` sha256
`0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` (re-verified) · seed `714559852`
· batch `85559852` · `source_ns=demo` · secrets by name only (`MONGODB_ATLAS_URI`,
`OW_BILLING_FIXTURE_DSN`, `OW_PG_DSN`, `AWS_ENDPOINT_URL`) · source concurrency cap 1 (all source
activity serial). Session: 2026-09-01 23:20 → 2026-09-02 00:12 UTC, parent machine.

This session converted nothing in wave 1 and did not read the children's diagnoses before re-running.
It extends the earlier wave-1 report (`tp-run/mongodb-20260901T205236Z--wave1-recon:.migration/recon/wave_reports/wave1.md`,
U3+U4 only) to all four wave-1 units, each **re-loaded by this session from the exact PR head** and
re-gated. Evidence: `wave1_part1_evidence/<unit>/` (gate `result.json`, gate/load logs, probe script,
`probes.json`, load report, unit-test log) and `wave1_part1_evidence/xunit/`.

---

## 1. Wave-close brief (one page)

**Wave verdict: PASS.** All four units PASS on the authoritative LIVE gate (`recon run`, the merge
authority) at their current PR heads, with every independent probe green except two explained
type-width flags on U4 (finding F-U4-1, not graded, value-exact). No fixture drift was observed: every
source population was re-read at least twice per unit (start / end of probes) and fingerprints matched.

| Unit | PR | Head attested (LIVE gate ran against a load from this SHA) | Gate (T1 / T2 / T3) | Probes | Verdict |
|---|---|---|---|---|---|
| U1 `customers`, `customers_history`, `counters` (+Q `dirty_signup_dt`, `bad_csv_list`) | #1430 | `c5baa80ab8afd54191b74854ca996fdf133e2c86` | PASS 3/3 · 313/313 · 33,333/33,333 (25,000 customers full diff + 8,333 graded embeds + 0 history) | 56/56 | **PASS** |
| U2 `invoices` (+Q `invoice_feed_orphan_lines`) | #1432 | `9643ce7658bc330afe4847d983cebf5033577cf1` | PASS 2/2 · 9/9 · 168,713/168,713 (18,750 invoices full diff + 149,963 graded embedded lines) | 62/62 | **PASS** |
| U3 `documents`, `document_snapshots` (+Q `orphan_document_snapshots`) | #1420 (merged) | `dfa5e9781e08718a7707a0a14ef9e8513149ed92` | PASS 3/3 · 18/18 · 16,260/16,260 (2,000 docs + 13,876 versions + 384 snapshots) | 65/65 | **PASS** |
| U4 `files` | #1419 (merged) | `3420f475c29b8889bc8676cebb58a9b4faabff2a` | PASS 1/1 · 12/12 · 10,000/10,000 full diff | 66/68 (2 explained flags, F-U4-1) | **PASS** |
| Cross-unit (U0 refs ↔ U1/U2, U3 ↔ U4, quarantine DB, RPT-114 replay) | — | — | — | 37/37 | PASS |

Quarantine (compared as SETS against source-derived expectations and the manifest): `dirty_signup_dt`
50/50, `bad_csv_list` 31/31, `invoice_feed_orphan_lines` 37/37 (verbatim rows equal),
`orphan_document_snapshots` 6/6 (verbatim), `files.orphaned_metadata` markers 40/40 (items migrated),
`documents.version_gaps` 10 docs / 10 missing numbers (preserved, not repaired). Nothing else in the
quarantine DB. Every quarantined doc carries a reason class.

**Findings needing orchestrator attention (none blocks the wave):**
- **F-U4-1 (low, code, not grading):** `files.size_bytes` is declared `bson_type: long` in the mapping
  but stored as BSON `int` (int32) for all 10,000 docs (`load_u4.py` `to_int` returns a Python `int`;
  pymongo picks int32 when the value fits — max fixture value 249,976,485). `version` is `int` as declared.
  Values are exact and every replayed file-service query is unaffected, and the harness treats
  int/long as one numeric class, so the gate cannot see it. Any item ≥ 2 GiB would silently become
  `long`, giving a mixed-width field. Same class as the earlier report's flag C; still open at `3420f475`.
- **F-U1-1 (informational):** U1 head moved twice during the session (`d1f69002` → `43e07061` →
  `c5baa80a`). The final delta changes `load_u1.py` (history extract follows mapping `root_where`,
  no batch filter) and `reports.py` (Oracle NULL-SUM semantics); this session re-loaded and re-gated
  from `c5baa80a` and the verdict is unchanged. Only a load from **this** SHA is attested.
- **F-U3-1 (spec ambiguity, grading-only — see §6):** the 0.5 % quarantine ceiling is "of a unit's root
  rows". U3 quarantines 6 of 390 snapshots (1.54 % of that collection, 0.25 % of the unit's 2,390 root
  rows, 0.037 % of all unit rows). Harness does not grade the ceiling; the planted count matches exactly.
- **F-XU-1 (source-side, informational):** the 50 `tenant_id` values on `CUSTOMER_MASTER`/`INVOICE_HEADER`
  (batch `85559852`) do not exist in `TENANTS` (69 ids) — identical on Oracle and Mongo (orphans 50/50),
  a fixture-seeding property, not a migration defect. Any `$lookup tenants` in later waves (U9
  `fn_overdue_accounts`) will hit the left-join-null path for every row of this batch.
- **F-U2-1 (source-side, informational):** 18,750/18,750 invoices have `total_amt ≠ Σ lines.amount`
  and 19,512 `(invoice_id,line_no)` groups are duplicated in `INVOICE_LINE` — identical on both sides.
- **Env note:** `services/legacy-billing/tests/test_reports.py` (touched by `c5baa80a`) could not be
  collected here (`flask` not installed in the recon venv); `test_load_u1.py` 13/13 passed. U4 has no
  unit tests on its head.

**Grading-only amendments recommended (NOT applied):** see §6 — (a) pin the quarantine-ceiling
denominator; (b) add a BSON `$type` histogram check to Tier 2 so declared width is graded.

**Per-unit cost (serial, parent machine):** U1 load 28 s + gate 94 s (+ prior-head gate 94 s and 87 s)
+ probes 45 s (76 Oracle stmts) ≈ 6 min total incl. the re-attestation; U2 load 65 s + gate 22 s / 24 s
+ probes 208 s (73 Oracle stmts) ≈ 5.5 min; U3 load 13 s + gate 6 s / 6 s + probes 11 s (99 pg stmts)
≈ 1 min; U4 load 31 s + gate 7 s / 6 s + probes 13 s (30 DynamoDB scans/gets, 2 full partition scans)
≈ 1 min; cross-unit 6.5 s ×2 (25 Oracle stmts + 1 pg pass each). No fixture restart or reseed.

---

## 2. Method

For each unit, in order: (1) re-fetch the PR head and check it out in an isolated worktree
(`~/wave_recon/heads/<unit>`; parent checkout untouched); (2) run the gate VERBATIM from
`03_mapping_spec` against the pre-existing target state (`gate_run1`); (3) re-load the target from the
head's loader (`scripts/tp_mongo/load_u<n>.py`, report written outside the repo); (4) re-run the gate
(`gate`), recording collection UUIDs before/after to prove no concurrent writer; (5) run the independent
probe script (source re-read at start and end; on any mismatch the source side is re-read twice before
calling drift vs defect — no mismatch required triage); (6) unit tests where present. Gate commands:

```
recon run --unit U1 --family oracle --mapping mapping_u1_subset.json --tolerances ../02_tolerances.json \
  --canonicalization ../canonicalization.json --mode live --source-dsn-secret OW_BILLING_FIXTURE_DSN \
  --target-uri-secret MONGODB_ATLAS_URI --target-db ow_tp_mongodb_205236 --seed 714559852 \
  --param batch_no=85559852 --param source_ns=demo --out gate                      # U2 identical with --unit U2
python .migration/recon_ext/recon_pg.py --unit U3 --family postgres ... --source-dsn-secret OW_PG_DSN ...
python .migration/recon_ext/run_dynamo_recon.py --unit U4 ... --source-endpoint-secret AWS_ENDPOINT_URL ...
```
`mapping_u<n>_subset.json` = the head's `03_mapping_spec.json` filtered to the unit's collections
(spec content unchanged); tolerances/canonicalization are the run-branch files (unchanged).

Source populations (read twice, stable): Oracle `CUSTOMER_MASTER` 25,000 · `ENTITY_ATTR_VALUE` 8,333
customer rows · `CUSTOMER_MASTER_HIST` 0 · `INVOICE_HEADER` 18,750 · `INVOICE_LINE` 150,000 (149,963 with
header, 37 orphans) · `CODES` 32 · `TENANTS` 69 · `PLANS` 3 · Postgres `documents` 2,000 ·
`document_versions` 13,876 · `document_snapshots` 390 (384 with parent) · DynamoDB `ns=demo` 10,000
(table ns histogram `{demo: 10000}`, hash key `id`, no GSIs).

---

## 3. Per-unit detail

### 3.1 U1 — `customers`, `customers_history`, `counters` (Oracle) — PASS @ `c5baa80a`

Gate: pre-existing state (`gate_run1`, head then `d1f69002`) PASS; after reload from `43e07061` PASS
(first attempt failed with `QueryPlanKilled: collection dropped` because the loader's drop/recreate was
still visible — no active ops, re-run PASS; recorded as transient, not data); after the head moved to
`c5baa80a` re-loaded and re-gated: **PASS** T1 3/3, T2 313/313, T3 33,333/33,333, UUIDs stable.
Load: customers 25,000, attributes 8,333, history 0, counters 3, Q 50 + 31.

Probes 56/56 (`probe_u1.py`): 155 root fields null/missing/empty distributions == source; BSON types
exact per declared type (`cust_seq_no` long, code fields int, decimals Decimal128 compared without
floats); `_id == cust_id`; no duplicate `(tenant_id,cust_no)`, `cust_no`, EAV, or sequence keys; boundary
(min/max) rows compared field-for-field; per-tenant aggregates; `attributes` array length histogram ==
EAV rows per customer, element invariants; quarantine `dirty_signup_dt` and `bad_csv_list` compared as
SETS of `cust_id` (50/50, 31/31) and verbatim values; derived CSV arrays/dates re-derived from verbatim
source strings; field set and `ns` exact; indexes exact (`tenant_id_1_cust_no_1` unique); empty-collection
behaviour (`customers_history` 0 rows → collection exists, indexes present, gate population 0);
`counters` == `USER_SEQUENCES` (125000 / 1 / 11001); customer↔invoice shared references; RPT-114
`BALANCES_SQL` replay (`25000, 39799450.31, 7330214.66` with FM formatting) and lookup/prefix-search
replays equal. Unit tests `test_load_u1.py` 13/13 (28/28 across u0/u1/u3 at the prior head).

### 3.2 U2 — `invoices` with embedded `lines` (Oracle) — PASS @ `9643ce76`

Gate: `gate_run1` PASS; reload (65 s) then **PASS** T1 2/2, T2 9/9, T3 168,713/168,713
(18,750 roots full diff + 149,963 graded embedded lines), UUIDs stable.

Probes 62/62 (`probe_u2.py`): root and embedded null/missing/empty-string distributions; BSON types
(`invoice_date`/`due_date` both date; decimals Decimal128); `_id == invoice_id`; duplicate `invoice_no`,
`line_id`, `(invoice_id,line_no)` — the same 19,512 duplicate groups exist on both sides (source
property); min/max/longest invoices compared fully; 200 random full invoices; Decimal128 on 300 random
lines; per-tenant and per-line-type sums; status/posted/source-system distributions; `lines` length
histogram == child rows per header (orphans excluded); denormalised parent references inside line
elements consistent; all-batch header check (37 quarantined `invoice_id`s absent from every batch);
quarantine `invoice_feed_orphan_lines` compared as a SET of `line_id` and verbatim rows (37/37,
0.025 % of 150,000 child rows); derived `gl_accounts` arrays and parsed dates; field set / `ns`;
indexes exact; empty-source and transform behaviour; references to `codes`/`customers`/`tenants`;
RPT-114 status and line rollups; application-style lookups; source stable. Tests 6/6 (U2-selected).

### 3.3 U3 — `documents` (+`versions`), `document_snapshots` (Postgres) — PASS @ `dfa5e978`

Gate: `gate_run1` PASS; reload (13 s) then **PASS** T1 3/3, T2 18/18, T3 16,260/16,260, UUIDs stable.

Probes 65/65 (`probe_u3.py`): null/missing per field (`folder_id` missing on 404 docs where source is
NULL — allowed by `null_missing_equiv`; recorded); BSON types for documents, versions, snapshots; UUIDs
lower-case hyphenated; no duplicate version or document keys; boundary + random full doc/version
comparisons; all 384 loaded snapshots compared, `state_b64` validated; timestamp precision (0/2000
source values needed sub-ms truncation); per-owner aggregates; content-type/boolean/folder
distributions; text and base64 length sums; `versions` length histogram == child rows per document;
`version_gaps` re-derived independently: exactly 10 documents, 10 missing numbers (preserved, not
repaired); no orphan versions in source; quarantine `orphan_document_snapshots` as a SET (6/6,
verbatim); field set / `ns` / indexes; empty-source behaviour (loader has no empty-source guard —
noted, not a data defect); owner/version/snapshot references; document-service replays (owner filter,
deleted/template filters, `updated_at` ordering, recent-5 versions, folder filter, version listing,
version→document lookup, latest snapshot) equal; source stable. Tests 9/9.

### 3.4 U4 — `files` (DynamoDB) — PASS @ `3420f475`

Gate: `gate_run1` PASS (existing state); reload via staging+rename (31 s, 10,000 inserted, 40 markers,
detection `s3_key_convention:/missing/` because bucket `otterworks-files` prefix `demo/` has 0 objects
— verified) then **PASS** T1 1/1, T2 12/12, T3 10,000/10,000 full diff, UUIDs stable.

Probes 66/68 (`probe_u4.py`): two consistent full partition scans + one after probes, fingerprint
equal; ids unique; table key schema `id` HASH, no GSIs; only partition `demo` exists (nothing to
exclude, but `source_ns`/`ns` are 100 % correct); no `files__u4_staging` residue; no U4 quarantine
collection (by contract); `_id` set == source id set; field set exact (12 mapped + `ns` +
`orphaned_metadata`), all present on every doc; null/missing/empty-string per field 0 == 0; **all 10,000
documents compared field-for-field** against a re-derivation from the mapping (0 mismatches);
boundary docs (`size_bytes` 2,117 / 249,976,485; `version` 1 / 9; dates; name; `_id`) equal; Σ
`size_bytes` 1,268,715,381,927 exact; histograms of owner (50), folder (10), mime (10), version (9),
`is_trashed` (9,461 / 539) equal; 0 sub-ms source timestamps, all UTC-marked; `orphaned_metadata`
SET == 40 planted `/missing/` keys == manifest, items migrated, 0.400 %; indexes exactly
`owner_id_1_is_trashed_1`, `folder_id_1`; empty-partition scan returns 0 and the loader refuses an empty
source (code-read, `load_u4.py:192-196`); file-service replays from `metadata.rs` (`list_files` by
owner / folder / owner+folder / incl. trashed, `list_trashed` all/owner, `get_file` ×25, per-owner
storage usage) equal. **Flags:** `types.exact_per_field` / `types.size_bytes_long_version_int` —
`size_bytes` stored as `int`, declared `long` (F-U4-1). No unit tests on this head.

---

## 4. Cross-unit consistency (37/37, `xunit/probe_xunit.py`, run after the final U1 reload)

- U0 refs: `codes` 32 / `tenants` 69 / `plans` 3 == Oracle; `codes` `(type,val,desc)` equal, `_key ==
  "TYPE:VAL"`; `plans.tier_cd` set and `tenants.status_cd` histogram equal.
- `tenants` ↔ U1/U2: customer and invoice `tenant_id` distinct sets equal (50), per-tenant counts equal;
  orphans vs `tenants._id` identical on both sides (50/50 — F-XU-1).
- `customers` ↔ `invoices`: invoice `cust_id` set (7,581) equal, 0 orphans on both sides, 0 invoice/
  customer tenant mismatches, per-customer `(count, Σ total_amt)` rollups equal (Decimal-exact).
- `codes` resolution: `status_cd`/`cust_type_cd`/`segment_cd`/`region_cd` distributions equal; unresolved
  `INV_STATUS` set empty on both sides.
- `counters` == `USER_SEQUENCES` after all wave-1 loads.
- **RPT-114 replay** (`reports.py` SQL verbatim on Oracle vs pipelines on Mongo, FM formatting):
  month-end by status (3 rows), by status × line type (12 rows incl. `COUNT(DISTINCT invoice_id)`), and
  reconciliation balances — all equal.
- U3 ↔ U4: document owner set == Postgres (50); doc/file owner pools disjoint as seeded; no `_id`
  collisions across `documents`/`files`/`document_snapshots`.
- Quarantine DB: exactly the four wave-1 classes with manifest counts; every doc has a reason class;
  U3/U4 marker counts (10 gap docs, 40 orphan markers) match manifest.
- Target DB inventory: exactly the 10 wave-0/1 collections; the two `*_205236*` databases only.

---

## 5. Drift-vs-defect triage

No gate or probe mismatch occurred, so no triage was required. Source stability was nonetheless proven
per unit by fingerprinting the source population at probe start and end (Oracle 2 passes/unit, Postgres
2 passes, DynamoDB 3 consistent scans) — all equal. The one operational failure (U1 `QueryPlanKilled`)
reproduced as a timing artefact of reading during the loader's drop/recreate and disappeared on re-run
with stable collection UUIDs.

---

## 6. Grading-only amendments (recommended, NOT applied — orchestrator decides)

1. **Quarantine-ceiling denominator (02_tolerances "≤ 0.5 % of a unit's root rows").** Record the
   operative reading as "root rows of the unit (all root collections summed)" so U3's 6/2,390 = 0.25 %
   is unambiguous, or, if the intent is per-collection, note U3 at 1.54 % is accepted because the class
   is a manifest-enumerated planted anomaly with exact count. Either way the gate is unaffected (the
   harness does not grade the ceiling); this only pins wording.
2. **Tier-2 BSON `$type` histogram per declared `bson_type`.** The harness collapses int/long/double/
   decimal to "numeric", so F-U4-1 (`size_bytes` int vs declared long) is invisible to the merge
   authority. A grading-only addition would make width drift a Tier-2 finding for later waves (U5–U9
   carry many `long` amounts/sequences). Not applied.

No tolerance, canonicalization or mapping value was changed by this session.
