# Wave 1 — independent reconciliation report (U3, U4)

> **Pass 2 (22:37–22:40 UTC) — current attested heads: U3 `dfa5e978` (merged into run branch),
> U4 `3420f475` (PR #1419, moved past the pass-1 SHA `51f7cca3`). Verdict unchanged: U3 PASS, U4 PASS,
> wave PASS.** Pass-2 detail is in §0 below; §1–§6 are the pass-1 report (U4 @ `51f7cca3`) kept as
> history — every pass-1 finding was re-checked in pass 2 and still holds. Evidence for pass 2 is in
> `wave1_evidence/pass2/<unit>/`.

## 0. Pass 2 — re-attestation at current heads

| Unit | Head attested | Load state | Gate (LIVE, verbatim) | Probes | Verdict |
|---|---|---|---|---|---|
| U3 `documents`, `document_snapshots` (+ quarantine `orphan_document_snapshots`) | `dfa5e9781e08718a7707a0a14ef9e8513149ed92` — unchanged since pass 1, merged into `tp-run/mongodb-20260901T205236Z` (`e9d78073`) | existing load from this head (loader unchanged) | **PASS** T1 3/3 · T2 18/18 · T3 16,260/16,260; `result.json` identical to the committed one on the branch | 33/36 ok; same 3 explained flags (A, B) | **PASS** |
| U4 `files` | `3420f475c29b8889bc8676cebb58a9b4faabff2a` — new head (review round 3: `key_strata` uses the mapped partition; endpoint redaction in load report; staging+rename loader) | **re-loaded by me from this head** (`scripts/tp_mongo/load_u4.py --source-ns demo`, 22:37:23→22:37:51, 10,000 inserted, strategy `stage into files__u4_staging, then rename over files (dropTarget)`) | **PASS** T1 1/1 · T2 12/12 · T3 10,000/10,000; `result.json` identical to the committed `.migration/recon/U4/gate/result.json` at the head | 29/30 ok; 1 flag (C) unchanged | **PASS** |
| **Wave 1** | | | | | **PASS** |

What changed between `51f7cca3` and `3420f475` (diff read before running): `load_u4.py` now converts
everything before any target write, loads into `files__u4_staging`, builds indexes there and renames
over `files` with `dropTarget` (previous `files` retained on failure); the load report now records only
the endpoint origin (no userinfo/path/query); `dynamo_source.py.key_strata` draws Tier-3 strata from
the mapped `root_where` partition instead of the whole table (no grading logic changed; still read-only,
secrets by name). Branch does **not** carry the run-branch grading amendment v1.0.1 (`40e7c54c`, codes key
expr) — irrelevant to U4 (`files` mapping unchanged; the gate ran with the branch's own spec v1.0,
`mapping_spec_sha256 050d230a…`).

Pass-2 additional probes for the new loader: no `files__u4_staging` residue; index names after rename
exactly `_id_`, `folder_id_1`, `owner_id_1_is_trashed_1`; all other collections' counts untouched by the
reload (codes 32 / tenants 69 / plans 3 / documents 2000 / document_snapshots 384); `source_ns=="demo"`
on 100 %; `s3_key`→`_id` bijection (10,000 distinct). Independent full value diff: 0 diffs; `size_bytes`
sum exact 1,268,715,381,927; orphaned_metadata SET == 40 planted; boundary docs equal; 78 replayed
file-service ops equal.

Cross-unit (pass 2): `ns=="mongo_205236"` on 100 % of all six target collections; U3 owner set (50)
== source (uuid lower-cased); U4 owner set (50) == source; U3∩U4 owners = ∅ (as seeded); neither U3
nor U4 carries fields referencing codes/tenants/plans. Drift triage: source re-counted twice (pg
2000/13,876/390, max(updated_at) 2026-08-01; DynamoDB consistent scan 10,000) — stable both passes.

Cost (pass 2, serial, parent machine): U4 loader ~28 s (1 DynamoDB scan) + gate ~7 s (1 cached
consistent scan) + probes ~15 s (1 scan); U3 gate ~6 s (count + 18 agg + full keyed fetch of 3
tables) + probes ~23 s (1 pass); cross-unit ~5 s (1 pg pass + 1 ddb scan). No fixture restart or
reseed; manifest sha256 re-verified `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`.

Grading-only amendments: **none warranted** (unchanged from §6).

---

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0** · tolerances **v1** · canonicalization **v1**
· target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) · secret `MONGODB_ATLAS_URI` (by name)
· mode **LIVE** on the parent machine's canonical fixtures (manifest sha256
`0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`, verified) · seed `714559852`
· params `batch_no=85559852 source_ns=demo` · source-load cap 1 honoured (gates + probes run serially,
one source connection at a time). Reviewer converted nothing in this wave and did not read the
children's diagnoses before re-running.

Units in this wave-close: **U3** (PR #1420, branch `--u3` @ `dfa5e978`) and **U4** (PR #1419,
branch `--u4` @ `51f7cca3`). Each gate was re-run from a clean checkout of the unit's own branch
(`~/wave_recon/otterworks`), against the unit's own load state already present in the target db.

## 1. Verdicts

| Unit | Gate (LIVE, re-run verbatim) | Tier checks (mine / child's) | Probes | Verdict |
|---|---|---|---|---|
| U3 `documents`, `document_snapshots` | **PASS** | T1 3/3 · T2 18/18 · T3 16,260/16,260 (full diff 2000 roots + 13,876 graded embed elems + 384 snapshots) | 33/36 ok; 3 flagged, all explained (§3) | **PASS** |
| U4 `files` | **PASS** | T1 1/1 · T2 12/12 · T3 10,000/10,000 (full diff) | 24/25 ok; 1 flagged, explained (§3) | **PASS** |
| **Wave 1 (U3+U4)** | | | | **PASS** |

Both re-runs reproduce the children's committed `result.json` exactly (same tier check counts, same
verdict, no warnings, no UNGRADED embeds). Children's evidence was generated in LIVE mode against
their own fixture boot; mine is the authoritative LIVE proof on the parent machine. Tier 4 does not
apply to U3/U4 (data units, no recorded ops file); app-level parity was replayed manually (§4).

Evidence: `wave1_evidence/<unit>/{result.json,report.md,recon.summary.md,probes.json,probe_*.py}`.

## 2. Gate invocations (verbatim, D13 adapter extensions from each unit's branch)

```
# U3 (branch --u3): PG_SRC_DSN named, value from env
python .migration/recon_ext/recon_pg.py --unit U3 --family postgres \
  --mapping .migration/03_mapping_spec.json --tolerances .migration/02_tolerances.json \
  --canonicalization .migration/canonicalization.json --mode live \
  --source-dsn-secret PG_SRC_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db ow_tp_mongodb_205236 \
  --seed 714559852 --param batch_no=85559852 --param source_ns=demo --unit-only --out <out>
# U4 (branch --u4): AWS_ENDPOINT_URL=http://localhost:4566 named
python .migration/recon_ext/run_dynamo_recon.py --unit U4 \
  --mapping .migration/03_mapping_spec.json --tolerances .migration/02_tolerances.json \
  --canonicalization .migration/canonicalization.json --mode live \
  --source-endpoint-secret AWS_ENDPOINT_URL --target-uri-secret MONGODB_ATLAS_URI --target-db ow_tp_mongodb_205236 \
  --seed 714559852 --param batch_no=85559852 --param source_ns=demo --out <out>
```
Harness: plugin `mongo-migration-plugin-6d021e15/0.2.1` `mongo-recon-harness` (fresh venv, `recon selftest` PASS).
Engine/tiers/tolerances/report are the harness's; only the source adapter is the D13 extension
(I read both adapters: read-only, secrets by name, C-collation min/max, uuid lower-casing — no grading logic).

Source pre-check (read-only): pg `documents`=2000, `document_versions`=13,876, `document_snapshots`=390
(6 orphans); DynamoDB `ns=demo`=10,000 (no other ns). Drift triage: source side re-counted twice
(pg counts + max(updated_at), ddb consistent COUNT scan) — identical both passes; no drift, no defect.

## 3. Adversarial probes (beyond the gate)

### U3 — 36 probes, 33 ok
| Probe | Result |
|---|---|
| Null/missing per field (documents, snapshots, versions[]) — src NULL count == tgt null+missing; empty-string counts equal | ok (only nullable field with NULLs: `documents.folder_id` 404) |
| Duplicate keys: `versions.id` global, (`_id`,`version_number`), `_id` type | ok — none |
| Embed length **per document** vs child rows (Tier 1 only sums globally) | ok — 0 mismatches; length histogram identical (2..12, min 2, max 12, avg ≈6.9) |
| Versions array ordered by `version_number` asc | ok |
| Field-set audit (no undeclared fields; `ns` on 100 %) | ok — exactly mapping fields + `versions`, `version_gaps`, `ns` |
| BSON types per field | **flag A** — `documents.folder_id` absent on 404 docs instead of explicit `null` |
| `explicit_null_policy (D2)` | **flag A** (same root cause; `document_snapshots.label` has 0 source NULLs so untested there) |
| Min/max boundary docs (created_at, updated_at, word_count, version, title, len(state_b64)), full-field compare | ok |
| `state_b64` byte-transparency: md5 of ordered concat + total length | ok (3,072 chars both sides) |
| Derived `version_gaps` (ungraded) recomputed from source | **flag B** — 10 docs flagged in target vs 8 by literal "1..max(version_number)" |
| Quarantine `orphan_document_snapshots` compared as SETS to source orphans | ok — 6 == 6, none in main, main ∪ quarantine == source ids, no overlap, single class `orphan_parent`, row payload byte-equal |
| Quarantine ceiling | 6/16,266 unit rows = 0.037 % (< 0.5 %); as share of the snapshots table alone 1.54 % — planted anomaly, expected 6 |
| Empty/edge: no doc without `versions[]`, no zero-length arrays (source min 2) | ok |
| Declared indexes present (`owner_id`, `folder_id`, `versions.id`; snapshots `(document_id, created_at desc)`) | ok |
| `document_snapshots.document_id` all resolve to a `documents._id` in target | ok |
| Distributions `is_deleted` (67/1933), `is_template`, `content_type` | ok |

### U4 — 25 probes, 24 ok
| Probe | Result |
|---|---|
| Independent full scan + key-set equality | ok — 10,000 == 10,000 |
| Attribute presence / null distribution; source shape (all items carry all 12 attributes) | ok — no nulls anywhere, no missing fields (`folder_id` never NULL in this fixture, so D2 policy untested here) |
| Field-set audit; `ns` and `source_ns` on 100 % | ok — mapping fields + `source_ns`, `ns`, `orphaned_metadata` |
| BSON types | **flag C** — `size_bytes` stored as `int` (int32) on all 10,000 docs; spec says `long` |
| Duplicates `s3_key`, `name` | ok — none either side |
| Independent full value diff (all items × all attributes, after canonicalization) | ok — 0 diffs |
| Boundary docs (size 2,117 .. 249,976,485; version; created/updated; name) | ok |
| `size_bytes` exact sum 1,268,715,381,927; values > int32: 0 | ok |
| Derived `orphaned_metadata` (ungraded) as SET vs seed rule (`s3_key` prefix `demo/missing/`) | ok — 40 == 40, expected 40 |
| `orphaned_metadata` vs S3 truth | not verifiable: LocalStack buckets hold no `demo/` file objects, so "absent in S3" is trivially true for all 10,000; the child's `s3_key` convention detector is the only workable rule on this fixture (informational) |
| Quarantine: none expected, none present for U4 | ok |
| Declared indexes `(owner_id,is_trashed)`, `folder_id` | ok |
| Distributions `is_trashed` (539 true), `mime_type` ×10, `version` 1..9 | ok |

### Flag analysis
- **A (U3, `folder_id` absent vs explicit null) — non-blocking, spec-conformance note.** D2 says
  "explicit BSON `null` for NULL/empty"; `load_u3.py` `transform_document`/`transform_snapshot` omit the
  key when NULL. The gate tolerates it because the mapping declares `null_missing_equiv` on `folder_id`
  and `label` (it therefore also *defers* those fields from Tier 2 to Tier 3, which passed). Query
  semantics are unaffected (`{folder_id: null}` matches both). Not data drift, not a grading issue;
  the orchestrator may want a review comment for D2 consistency across units (U1/U2 emit explicit nulls
  per D2 — worth checking uniformly at cutover).
- **B (U3, `version_gaps` 10 vs 8) — DRIFT-EXPLAINED, in the unit's favour.** The loader defines the
  range as `1..max(documents.version, max(version_number))`; the literal spec text says "between 1..max".
  Two planted gaps skip the *last* version (`54f581c5` versions 1–5 with root.version 6; `cf385bde` 1–2
  with root.version 3), which only the loader's definition can see. It matches the manifest's planted
  count (10) exactly, and the field is derived/ungraded and "reported, never repaired". No action.
- **C (U4, `size_bytes` int32 vs declared `long`) — non-blocking, type-conformance note.** `load_u4.py`
  maps `("N","long") -> to_int` (plain Python `int`); pymongo encodes values that fit in int32 as BSON
  `int`. Values are exact (independent diff 0, sum exact) and the harness does not grade BSON width, so
  the gate is unaffected. Risk is schema-shape only: a future item > 2^31−1 would be auto-promoted to
  `long`, giving a mixed-type field; `bson.Int64` would make the declared type hold. Recommend a review
  comment on PR #1419; not a gate failure and I did not change it.

## 4. Cross-unit consistency and app-level replay
- `ns == "mongo_205236"` on 100 % of docs in all six collections of the target db (U0 codes 32 /
  tenants 69 / plans 3 untouched by the wave-1 loads; U3 2000+384; U4 10,000).
- U3 internal references: `documents.owner_id` set (50) == source; `versions[].created_by` (50) ⊆ owners
  and == source; `document_snapshots.created_by` (48) == source. U3 and U4 owner/folder sets are
  disjoint by construction (separate seeded RNG streams per store) — identical on both sides.
  U3/U4 do not reference `codes`/`tenants`/`plans`; nothing to cross-check there.
- Replays (source SQL / DynamoDB scan semantics vs Mongo, identical result sets):
  - `document_service.list_documents` (is_deleted=false ∧ is_template=false, optional owner/folder,
    order updated_at desc, page 1–2 × size 20): 24 ops, counts and id order equal.
  - `recent_versions` (top-5 by version_number desc), `list_versions` (asc), `get` (is_deleted filter):
    60 documents, equal. `search` (ilike on title/content, 4 terms incl. no-match): equal.
    Latest snapshot per document (`document_id, created_at desc`): 50 docs, equal.
  - `file-service metadata.rs list_files(folder?, owner?, include_trashed)`: 24 ops equal;
    `list_trashed` (sorted updated_at desc, optional owner): 4 ops equal; `get_file`: 50 ok;
    `etl/storage_cleanup_daily` s3_key reference set: equal.

## 5. Cost line (this reviewer, parent machine, serial)
| Unit | Gate wall-clock | Probe wall-clock | Source passes | Target reads |
|---|---|---|---|---|
| U3 | ~26 s (22:01:07→22:01:33) | ~30 s | 1 gate (count + 18 agg + full keyed fetch of 3 tables) + 1 probe pass + 2 drift re-counts | full scans of 2 collections ×~3 |
| U4 | ~5 s (22:01:48→22:01:53; single cached consistent scan) | ~17 s | 1 gate scan + 1 probe scan + 2 COUNT scans | full scan ×2 |
Setup: venv + harness install ~1 min; no fixture restart or reseed was needed (all containers healthy).

## 6. Grading-only amendments (described, NOT applied)
1. **None required for the verdict.** Both gates are green as specified.
2. Suggested for the orchestrator's consideration (profile/mapping feedback, not tolerance changes):
   - Record in `05_decisions.md` the operative `version_gaps` definition
     (`1..max(documents.version, max(version_number))`) so the derived-field text in the mapping spec
     ("1..max") is unambiguous for cutover re-checks (flag B).
   - The harness does not grade BSON type width; if the estate wants declared `bson_type` enforced, that
     is PROFILE FEEDBACK for the plugin (a Tier-2 `$type` histogram check), not a change here (flag C).
   - D2 explicit-null policy vs `null_missing_equiv`: decide once whether "missing" is acceptable
     estate-wide (then D2 wording is loose) or explicit null is required (then U3 needs a one-line loader
     change before cutover). Neither affects this wave's PASS.

---

# Wave-1 close brief (one page)

**Verdict: WAVE 1 (U3, U4) PASS — LIVE, independently reproduced on the parent machine.**
**Attested heads (pass 2): U3 `dfa5e978` (merged), U4 `3420f475` (re-loaded from this head, then gated).**

- **What was checked.** Both unit gates re-run verbatim from each PR branch's own code against the
  canonical fixtures (manifest checksum verified) and the units' already-loaded target collections.
  U3: 16,281 harness checks across 3 tiers (full diff, embeds value-graded, no UNGRADED). U4: 10,013
  checks (full diff). Results identical to the children's committed evidence. 61 additional adversarial
  probes: null/missing per field, duplicate keys, per-document embed cardinality, boundary docs,
  byte-hash of the large payload column, quarantine as sets, derived-field recomputation, field-set
  and BSON-type audits, index presence, `ns` marker, cross-unit reference sets, and 216 replayed
  app-level operations from `document-service` and `file-service` — all equal.
- **Data fidelity.** Zero value differences on either unit. Quarantine `orphan_document_snapshots`
  = exactly the 6 planted orphans (set-equal, payload-equal, none leaked into the main collection).
  `orphaned_metadata` markers = exactly the 40 planted. Version gaps = exactly the 10 planted.
- **Findings (none blocking).** (A) U3 writes NULL `folder_id`/`label` as *absent* rather than explicit
  BSON null — deviates from D2 wording, tolerated by the mapping's `null_missing_equiv`, no query impact.
  (B) `version_gaps` uses `max(root.version, max(version_number))` — explained drift vs the literal spec
  text, and the correct reading (catches trailing gaps; matches manifest). (C) U4 `size_bytes` lands as
  int32 rather than declared `long`; values exact; schema-shape risk only. Recommend review comments
  on #1420 (A) and #1419 (C); no code was changed by this reviewer.
- **Drift triage.** Source re-counted twice on both stores; stable. No fixture restart/reseed performed.
- **Ready for merge** per harness authority (`result.json` PASS ×2). Grading-only amendments: none
  needed; three profile/decision-log clarifications suggested above for the orchestrator.
