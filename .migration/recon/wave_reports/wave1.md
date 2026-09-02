# Wave 1 — independent reconciliation report, Part 1 (U3, U4) — carry-forward attestation

Run `tp-run/mongodb-20260901T205236Z` (head `da6e6ad2` at time of writing) · mapping **v1.0** · tolerances **v1**
· canonicalization **v1** · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`)
· secret `MONGODB_ATLAS_URI` (by name) · recon params `--seed 714559852 --param batch_no=85559852
--param source_ns=demo` · parent machine, canonical fixtures (Oracle `localhost:52521/FREEPDB1` ow_billing,
Postgres `localhost:5432/otterworks` schema `otterworks_demo`, LocalStack DynamoDB `localhost:4566`
`otterworks-file-metadata`; manifest sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`).
Session: 2026-09-02, independent reviewer; converted nothing in this wave; did not read the children's
diagnoses. Work done from a separate clone/worktree under `~/wave_recon/` (parent checkout untouched;
no fixture restart, reseed or data modification; no shells restarted).

## 1. Wave-close brief (one page)

**Wave verdict: PASS (carried).** Both wave-1 units under review are **already merged into the run
branch at exactly the PR heads given**, so — per the wave-close rule ("units whose PR is already merged:
attest the merged head and carry the PASS from the prior wave report for that head") — no LIVE source
window was opened this session and neither unit was re-graded. The LIVE window was not needed: there
are no unmerged units in this wave.

| Unit | PR | Head attested (CURRENT branch head == merged head) | Merge commit on run branch | Prior LIVE grading of this exact head (cited) | Verdict |
|---|---|---|---|---|---|
| U3 `documents`, `document_snapshots` (+Q `orphan_document_snapshots`) | #1420 | `dfa5e9781e08718a7707a0a14ef9e8513149ed92` | `811aed6f` (second parent = `dfa5e978`) | `--wave1-recon:.migration/recon/wave_reports/wave1.md` §0 (pass 2, PASS T1 3/3 · T2 18/18 · T3 16,260/16,260, 33/36 probes ok / 3 explained) and `--wave1-recon-part1:…/wave1.md` §3.3 (re-loaded from `dfa5e978`, PASS same tiers, probes 65/65) | **PASS (carried)** |
| U4 `files` | #1419 | `3420f475c29b8889bc8676cebb58a9b4faabff2a` | `cdb0abd4` (second parent = `3420f475`) | `--wave1-recon:…/wave1.md` §0 (pass 2, re-loaded from `3420f475`, PASS T1 1/1 · T2 12/12 · T3 10,000/10,000, 29/30 probes / 1 explained) and `--wave1-recon-part1:…/wave1.md` §3.4 (re-loaded from `3420f475`, PASS same tiers, probes 66/68, 2 explained type-width flags F-U4-1) | **PASS (carried)** |
| **Wave 1 (U3+U4)** | | | | | **PASS** |

Verification performed this session (git + target-only, zero source reads):
- `git fetch origin --prune`; `refs/heads/tp-run/mongodb-20260901T205236Z--u3` = `dfa5e978…`,
  `--u4` = `3420f475…` — identical to the heads graded LIVE in both prior reports (no head movement).
- `git merge-base --is-ancestor` of each head into `origin/tp-run/mongodb-20260901T205236Z`: **MERGED**
  for both; merge commits `811aed6f` (#1420) and `cdb0abd4` (#1419) carry the heads as second parents.
- Committed harness evidence on the run branch: `.migration/recon/U3/result.json` (unit U3, verdict
  PASS, mode live) and `.migration/recon/U4/gate/result.json` (unit U4, verdict PASS, mode live) —
  the same artefacts the prior LIVE re-runs reproduced byte-for-byte.
- Target load state still equals the attested one (`wave1_part1_carry_evidence/target_state_check.txt`):
  documents 2,000 / document_snapshots 384 / files 10,000 (all `ns == mongo_205236`); quarantine
  `orphan_document_snapshots` 6; `files.orphaned_metadata` markers 40; `version_gaps` docs 10;
  expected indexes present; no `files__u4_staging` residue. Nothing was re-loaded (loaded data does
  not predate the heads: U4 was loaded from `3420f475` and U3 from `dfa5e978` in the cited sessions).

**Open findings carried (none blocking, unchanged since the cited reports):**
- **F-U4-1 / flag C (low, code, not grading):** `files.size_bytes` declared `bson_type: long` in the
  mapping but stored int32 (values exact; harness treats int/long as one numeric class). Still present
  at `3420f475` (merged). Recommend a follow-up ticket rather than a re-open of #1419.
- **Flag A (U3):** NULL `folder_id`/`label` stored as absent rather than explicit BSON null; tolerated by
  `null_missing_equiv`; D2 wording ambiguity for the decision log.
- **Flag B (U3):** `version_gaps` uses `1..max(root.version, max(version_number))` — the correct
  reading; matches the manifest's 10 planted gaps; spec text should say so.
- **F-U3-1 (spec ambiguity, grading-only):** quarantine-ceiling denominator ("of a unit's root rows")
  — U3 quarantines 6/390 snapshots (1.54 % of that collection, 0.25 % of unit root rows).

**Per-unit cost (this session):** U3 — 0 source reads, 0 loader runs, ~2 s of target-only counts;
U4 — 0 source reads, 0 loader runs, ~2 s of target-only counts; git verification ~10 s. Source-load cap
1 honoured trivially (no source connection was opened). Prior-session LIVE costs for these heads are in
the cited reports (U3 gate ~6 s + probes ~11–23 s; U4 load ~28–31 s + gate ~6–7 s + probes ~13–15 s).

**Grading-only amendments (described, NOT applied):** none newly warranted. The two previously
suggested items remain for the orchestrator: (a) pin the quarantine-ceiling denominator in the tolerance
text; (b) a Tier-2 BSON `$type` histogram check so declared width (`long` vs `int`) is graded — profile
feedback for the plugin, not a tolerance change.

## 2. Why no LIVE re-run

The instruction for this pass is explicit: merged units are attested at the merged head and carry the
PASS from the prior wave report for that head; the LIVE window is reserved for unmerged units. Both
wave-1 units are merged at their current heads, so re-running the gates would consume the single
source-load slot for no new information. Should the orchestrator want a fresh LIVE proof anyway, the
verbatim gate invocations are recorded in `--wave1-recon-part1:.migration/recon/wave_reports/wave1.md` §2
and can be replayed against the current target state without reloading.

## 3. Evidence

- `wave1_part1_carry_evidence/attested_heads.json` — heads, merge commits, verdicts.
- `wave1_part1_carry_evidence/target_state_check.txt` — target-only state read.
- Prior LIVE evidence (cited, not copied): branch `tp-run/mongodb-20260901T205236Z--wave1-recon`
  (`wave1_evidence/pass2/{U3,U4}/`) and branch `tp-run/mongodb-20260901T205236Z--wave1-recon-part1`
  (`wave1_part1_evidence/{U3,U4}/`, `xunit/`).
