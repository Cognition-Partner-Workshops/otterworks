# Wave 1 — independent reconciliation report, Part 1 (U1, U2, U3, U4) — pass 3: U2 re-graded at `9e73ffea`

Run `tp-run/mongodb-20260901T205236Z` (head `754b8303` at fetch time) · mapping **v1.0** (run-branch
`03_mapping_spec.json`, file version tag `v1.0.1`, unchanged between the U2 heads) · tolerances **v1** ·
canonicalization **v1** (both byte-identical to the files gated in every prior wave-1 pass) · target
`ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · `ns = mongo_205236` · secret
`MONGODB_ATLAS_URI` (name only; fixture DSNs `OW_BILLING_FIXTURE_DSN`, `OW_PG_DSN`, `AWS_ENDPOINT_URL` by
name) · mode **LIVE** on the canonical fixtures (Oracle `localhost:52521/FREEPDB1` user `ow_billing`,
Postgres `localhost:5432/otterworks` schema `otterworks_demo`, LocalStack DynamoDB `localhost:4566` table
`otterworks-file-metadata`) · manifest `testdata/legacy/manifests/demo.json` sha256
`0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89` (re-verified on the parent checkout) ·
recon params `--seed 714559852 --param batch_no=85559852 --param source_ns=demo` · source-load cap 1 (all
source activity serial; this session was the only LIVE window). Session 2026-09-02 05:04 → 05:20 UTC,
parent machine, separate clone/worktrees under `~/wave_recon/` (parent checkout untouched; no fixture
restart, reseed or data modification; no shells restarted). This session converted nothing in wave 1 and
did not read the children's diagnoses before re-running. Evidence: `wave1_part1_u2_evidence/`.

---

## 0. Wave-close brief (one page)

**Wave verdict: PASS.** Three units (U1, U3, U4) are merged into the run branch at exactly their current
PR heads and carry their prior LIVE PASS. The one unmerged unit, **U2 (#1432)**, moved its head from the
previously attested `9643ce76` to **`9e73ffea`**; this session **re-loaded the target from `9e73ffea` and
re-ran the LIVE gate against that load: PASS** (T1 2/2 · T2 9/9 · T3 168,713/168,713 — 18,750 invoices full
diff + 149,963 graded embedded lines), independent probes **62/62**, cross-unit probes **37/37**, the head's
unit tests 7/7, and the head's own report builder PASS on this session's artefacts. No drift, no defect,
no triage required.

| Unit | PR | Current PR-branch head (attested) | Merged into run? | LIVE evidence for this head | Verdict |
|---|---|---|---|---|---|
| U1 `customers`, `customers_history`, `counters` (+Q `dirty_signup_dt`, `bad_csv_list`) | #1430 | `c5baa80ab8afd54191b74854ca996fdf133e2c86` | **yes** (merge `e87de328`) | carried — `tp-run/mongodb-20260901T205236Z--wave1-recon-part1:.migration/recon/wave_reports/wave1.md` §3.1 (commit `475560d4`): re-loaded from `c5baa80a`, LIVE gate PASS T1 3/3 · T2 313/313 · T3 33,333/33,333, probes 56/56 | **PASS (carried)** |
| U2 `invoices` + embedded `lines[]` (+Q `invoice_feed_orphan_lines`) | #1432 | **`9e73ffea31f41f37e10259a36f26b8be1f26da3b`** | **no** | **this session** — re-loaded from `9e73ffea` (65 s), LIVE gate PASS T1 2/2 · T2 9/9 · T3 168,713/168,713, probes 62/62, xunit 37/37 (§2) | **PASS** |
| U3 `documents` (+`versions[]`), `document_snapshots` (+Q `orphan_document_snapshots`) | #1420 | `dfa5e9781e08718a7707a0a14ef9e8513149ed92` | **yes** (merge `811aed6f`) | carried — same report §3.3: re-loaded from `dfa5e978`, LIVE gate PASS T1 3/3 · T2 18/18 · T3 16,260/16,260, probes 65/65 | **PASS (carried)** |
| U4 `files` | #1419 | `3420f475c29b8889bc8676cebb58a9b4faabff2a` | **yes** (merge `cdb0abd4`) | carried — same report §3.4: re-loaded from `3420f475`, LIVE gate PASS T1 1/1 · T2 12/12 · T3 10,000/10,000 full diff, probes 66/68 (2 explained type-width flags, F-U4-1) | **PASS (carried)** |
| Cross-unit (U0 refs ↔ U1/U2, U3 ↔ U4, quarantine DB as sets, RPT-114 replay) | — | — | — | **this session** 37/37 (§3) | PASS |

Head attestation (`git fetch origin --prune` 05:04:28 UTC; `wave1_part1_u2_evidence/heads.json`):
`origin/…--u1` = `c5baa80a`, `--u2` = `9e73ffea`, `--u3` = `dfa5e978`, `--u4` = `3420f475`; run-branch head
`754b8303`. `git merge-base --is-ancestor` → U1/U3/U4 merged, U2 not. U1/U3/U4 heads are byte-identical to the
heads the cited report re-loaded from and gated LIVE, so the carried verdicts describe exactly this code.

**What changed in U2 between `9643ce76` (previous LIVE PASS) and `9e73ffea`:** (a) merge of the run branch
(U1, U5–U9 code and evidence — nothing in U2's mapping, tolerances, canonicalization); (b) `load_u2.py`
+5 lines: refuse to replace the target when `INVOICE_HEADER` has no rows for the batch (the empty-batch
guard this reviewer flagged as missing in the prior report, probe 11.4); (c) `recon_report_u2.py`: the
quarantine-rate check tolerates a zero-invoice target (`None` instead of `ZeroDivisionError`);
(d) the child's re-run evidence under `.migration/recon/U2/`. The loaded **`invoices` collection produced
by `9e73ffea` is byte-identical to the one produced by `9643ce76`** (sorted canonical extended-JSON sha256
`ad20cc1e…` on both, 18,750 docs, same 4 indexes — `fp_before_load.json` vs `fp_after_load.json`); the
quarantine collection differs only in the per-load `quarantined_at` timestamp (37 docs, verbatim rows
re-verified against Oracle, probe 7.3).

**Quarantine (as SETS vs source-derived expectations and the manifest):** `invoice_feed_orphan_lines`
37/37 (`line_id` set == Oracle anti-join set, rows verbatim, 0.025 % of 150,000 child rows; the 37 orphan
`invoice_id`s resolve to no header in *any* batch); whole quarantine DB still exactly the four wave-1 classes
`dirty_signup_dt` 50 / `bad_csv_list` 31 / `invoice_feed_orphan_lines` 37 / `orphan_document_snapshots` 6,
every doc with a reason class; U3/U4 markers 10 / 40 == manifest.

**Findings (none blocks the wave):**
- **F-U2-2 (informational, closes a prior note):** the empty-batch refusal guard is now present and sits
  *before* `drop_collection` in `load_u2.run` (probe 11.4, verified by source position; not exercised against
  the live target — exercising it would require pointing the loader at an empty batch, which by design
  aborts before writing). The loader still drops the live `invoices` collection before re-inserting (no
  staging swap, probe 11.3 design note): a reader during the ~60 s load sees an empty/partial collection.
  U1/U4/U5 use staging+rename; U2 does not. Not a data defect; cutover-runbook item.
- **F-U2-1 (source-side, carried):** 18,750/18,750 invoices have `total_amt ≠ Σ lines.amount` and 19,512
  `(invoice_id, line_no)` groups are duplicated in `INVOICE_LINE` — identical on both sides (probes 3.3, 5.3).
- **Carried, unchanged:** F-U4-1 (`files.size_bytes` stored int32 vs declared `long`, value-exact,
  gate-invisible), F-U3-1 (quarantine-ceiling denominator wording), F-XU-1 (the 50 batch `tenant_id`s absent
  from `TENANTS` on both sides — re-confirmed 50/50 this session), F-U1-1 (informational).
- **Env note:** the target DB now also holds the wave-2/3 collections (`billing_*`, `credit_notes`,
  `dunning_attempts`, `notifications`, `rating_periods`, `subscriptions*`, `usage_events`, `replay_*`);
  the U2 reload touched only `invoices` and `invoice_feed_orphan_lines` (collection UUIDs of all other
  collections unchanged before/after load and before/after gate — `uuids_*.txt`). No U2 staging residue.

**Grading-only amendments recommended (NOT applied):** unchanged from the prior report §6 — (a) pin the
quarantine-ceiling denominator ("root rows of the unit, all root collections summed"); (b) Tier-2 BSON
`$type` histogram per declared `bson_type` so width drift (F-U4-1) becomes gradable. No new amendment.

**Per-unit cost (serial, parent machine):** U2 — Mongo pre-fingerprint 12 s, load 65 s (1 Oracle extract of
18,750 headers + 150,000 lines), gate 22 s (harness LIVE: full diff), probes 204 s (73 Oracle statements,
source population read at start and end), head report-builder check 3 s, unit tests <1 s ≈ **5.2 min**;
cross-unit 6.3 s (25 Oracle statements + 1 Postgres pass); U1/U3/U4 — 0 s source, 0 loads, 0 gates (git
attestation only; the U1/U3/U4 collections were verified untouched via UUIDs and the xunit probes:
`counters` == `USER_SEQUENCES`, `customers` 25,000, `documents` owner set, quarantine classes). Wall clock
≈ 16 min incl. report.

---

## 1. Method

1. `git fetch origin --prune`; record the four PR-branch heads and the run-branch head; `merge-base
   --is-ancestor` per unit (`heads.json`).
2. U2 only (unmerged): check out `9e73ffea` detached in `~/wave_recon/heads/u2` (worktree of the separate
   clone). Confirm the head's `02_tolerances.json` / `canonicalization.json` are byte-identical to the
   run-branch copies used in every prior pass (sha256 `d67ccdda…` / `527cf87c…`) and that the U2 projection
   of the head's `03_mapping_spec.json` (`mapping_u2_subset.json`, collections filtered to `unit == "U2"`,
   content unchanged) is identical to the prior pass's.
3. Fingerprint the pre-existing U2 target state (loaded by the prior session from `9643ce76`); record all
   collection UUIDs.
4. Re-load from the head: `python scripts/tp_mongo/load_u2.py --report-out <outside repo>` (defaults:
   `--batch-no 85559852`, secrets by name). 65 s; `invoices` 18,750 / embedded 149,963 / quarantined 37;
   only the two U2 collections' UUIDs changed.
5. Gate, VERBATIM from the spec, against that load (`gate/`):
   ```
   recon run --unit U2 --family oracle --mapping mapping_u2_subset.json --tolerances ../02_tolerances.json \
     --canonicalization ../canonicalization.json --mode live --source-dsn-secret OW_BILLING_FIXTURE_DSN \
     --target-uri-secret MONGODB_ATLAS_URI --target-db ow_tp_mongodb_205236 --seed 714559852 \
     --param batch_no=85559852 --param source_ns=demo --out gate
   ```
   Collection UUIDs recorded before and after the gate (identical → no concurrent writer).
6. Independent probes (`probe_u2.py`, this reviewer's script from the prior pass with probe 11.4 updated to
   check the new guard), cross-unit probes (`probe_xunit.py`), head unit tests, and the head's
   `recon_report_u2.build()` executed on *this session's* gate result and load report (with the prior
   session's `9643ce76` load report as "run 1" for the idempotency comparison) plus a synthetic zero-invoice
   target to exercise the changed branch.

## 2. U2 — `invoices` with embedded `lines[]` (Oracle) — PASS @ `9e73ffea`

**Gate:** `recon PASS: unit=U2 mode=live mapping=v1.0.1 tolerances=v1` · generated
2026-09-02T05:06:53Z · Tier 1 `counts_through_mapping` 2 checks PASS · Tier 2 `per_field_aggregates` 9 checks
PASS (6 key/date fields deferred to Tier 3 as designed) · Tier 3 `keyed_diffs` 168,713 checks PASS —
`invoices` mode `full_diff`, population 18,750; `embeds_graded.invoices.lines` 149,963 · warnings `[]`.
UUIDs stable across the gate (`uuids_before_gate.txt` == `uuids_after_gate.txt`).

**Probes 62/62** (`probes.log`, `probes.json`; 73 Oracle statements, 204 s):
- Null / missing / empty-string distributions: 9 root fields and 20 embedded fields (149,963 elements) equal
  to source NULL counts (only `POSTED_YN` 29,937 NULLs); no MISSING fields, no empty strings (explicit-null
  policy honoured).
- BSON types per declared type (root + embedded; decimals Decimal128 compared without floats; both derived
  dates BSON `date`); `_id` string == `invoice_id` on 18,750/18,750.
- Duplicate keys: `invoice_no` 0 groups both sides; `line_id` unique across all embedded elements; the same
  19,512 `(invoice_id, line_no)` duplicate groups on both sides (source property); no `line_id` both embedded
  and quarantined.
- Boundary docs: 32 keys (MIN/MAX per field, longest invoices with 23 lines, the 5 zero-line invoices)
  compared in full (32 × 9 root fields + 274 lines × 20 fields); 200 random invoices in full (1,581 lines);
  Oracle `TO_CHAR` vs Decimal128 on 300 random lines × 4 money fields.
- Aggregates spot-checked at doc level: per-tenant `SUM(total_amt)`/`COUNT` (50 tenants), per
  (tenant, line_type) `SUM(amount)`, `SUM(tax_amt)`, `COUNT` (200 groups), `status_cd` / `posted_yn` /
  `src_system` distributions equal.
- Embed-array length distribution == child rows per header (max 23, 5 empty); `lines` is an array on every
  doc; every element's `invoice_id`/`batch_no`/`tenant_id`/`cust_id` equals the parent; elements sorted by
  `(line_no, line_id)`; whole `INVOICE_LINE`/`INVOICE_HEADER` inside the batch (no other-batch rows).
- Quarantine `invoice_feed_orphan_lines` as a SET: 37/37, symmetric difference empty; docs carry `ns`,
  `unit`, `batch_no`, `reason_class = orphan_parent`, verbatim 20-field row; rows verbatim == source; orphans
  resolve to no header in any batch; ceiling 0.025 %; embedded + quarantined == 150,000.
- Derived fields: `gl_accounts` == trimmed CSV split (null → `[]`); `invoice_date`/`due_date` == Oracle
  `TO_DATE(...,'DD-MON-YY')` on 400 random headers; 0 unparseable dates on both sides.
- Field set exact (no `status_desc` persisted, per spec), `ns == mongo_205236` and `batch_no == 85559852`
  on 100 %; indexes exactly the 3 declared + `_id`, no unique flags.
- Empty-collection behaviour: `partition_lines([])` → nothing; `build_invoice_doc` edge cases (empty string →
  null, bad date → null, `lines == []`, `ROUND_HALF_EVEN`); **new guard at `9e73ffea` refuses an empty batch
  before dropping the target** (probe 11.4; `batch_no = 1` has 0 headers in source).
- Shared references: `codes` == Oracle `CODES` (32); `status_cd` → `INV_STATUS` unresolved set empty both
  sides; `line_type_cd` ∈ {1,2,3,9}; invoice `tenant_id` set ⊂ customers' (50) and resolves to `tenants` for
  0/50 on both sides (F-XU-1); `cust_id` → `customers` unresolved 0 (7,581 distinct); line `cust_no`/
  `cust_name` denorm disagreements 0 both sides.
- App-level replays: RPT-114 month-end STATUS rollup (3 rows: issued 5,504 / 55,450,955.92; overdue
  2,748 / 27,585,416.69; paid 10,498 / 104,582,085.97) and LINE rollup (12 rows incl. `COUNT(DISTINCT
  invoice_id)`) identical, FM formatting; lookup by `invoice_no` (25), invoices per customer (10),
  `line_id` → parent (25), orphan `line_id`s not findable in `invoices`.
- Source stability: header/line counts and `FIXTURE_META.initialized_at` (2026-09-01 20:53:10.961888)
  identical at probe start and end.

**Head tooling:** `scripts/tp_mongo/tests/test_load_u2.py` 7/7 (`unit_tests.log`). `recon_report_u2.build()`
from the head on this session's gate + load report → PASS, `quarantine_rate 0.00197`, idempotency vs the
`9643ce76` load `pass`; synthetic zero-invoice target → `quarantine_rate None`, five count checks fail
loudly, no exception (`recon_report_u2_build.log`, `u2.recon.head_build.json`).

## 3. Cross-unit consistency (37/37, `xunit/probes.log`, run after the U2 reload)

U0 refs `codes` 32 / `tenants` 69 / `plans` 3 == Oracle, `(type,val,desc)` equal, `_key` format;
`tenants` ↔ U1/U2 tenant sets (50) and per-tenant counts equal, orphans 50/50 both sides; `customers` ↔
`invoices` `cust_id` set 7,581, 0 orphans, 0 tenant mismatches, per-customer `(count, Σ total_amt)` equal;
code-resolution distributions for invoices and customers equal; `counters` == `USER_SEQUENCES`
(125000 / 1 / 11001); RPT-114 month-end (3 + 12 rows) and reconciliation balances
`(25000, 39799450.31, 7330214.66)` equal; U3 ↔ U4 owner sets / no `_id` collisions; quarantine DB exactly
the four wave-1 classes with manifest counts, every doc with a reason class, U3/U4 markers 10 / 40; all ten
wave-0/1 collections present, no `invoices*` staging residue (later-wave collections present as expected).

## 4. Drift-vs-defect triage

No gate or probe mismatch occurred; no triage was required. Source stability was nonetheless proven: the
Oracle population was read at probe start and end (probe 14.1) and the previous load (`9643ce76`) and this
load (`9e73ffea`) produced byte-identical `invoices` collections, so the source did not change between the
two LIVE passes either.

## 5. Grading-only amendments (recommended, NOT applied)

Unchanged from `--wave1-recon-part1` §6: (1) pin the quarantine-ceiling denominator; (2) Tier-2 BSON `$type`
histogram per declared `bson_type`. Nothing in this pass motivates a new one. No tolerance, canonicalization
or mapping value was changed by this session; no migrated or legacy code was touched.
