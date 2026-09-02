# Wave 0 — independent reconciliation report, Part 1 (U0) — merged-unit attestation

Run `tp-run/mongodb-20260901T205236Z` · mapping **v1.0.1** (v1.0 + grading-only key-expression amendment,
`03_mapping_spec.json` sha256 `57de55f24c241c51…`) · tolerances **v1** (`d67ccdda431baa5d…`) · canonicalization
**v1** (`527cf87c699275bd…`) · target `ow_tp_mongodb_205236` (quarantine `ow_tp_mongodb_205236_quarantine`) ·
secrets by NAME only (`MONGODB_ATLAS_URI`, `OW_BILLING_FIXTURE_DSN`) · mode **LIVE** on the parent machine's
canonical fixtures (Oracle `localhost:52521/FREEPDB1` user `ow_billing`; manifest
`testdata/legacy/manifests/demo.json` sha256 `0f4722866117edd2ea1f5cf933b294bf39a52c755cff222a3a3c6ca5e8e2ee89`
re-verified) · seed `714559852` · params `batch_no=85559852 source_ns=demo` · source-load cap 1 honoured (one
Oracle connection at a time; gate and probes serial). Session 2026-09-02 ≈04:10 → 04:30 UTC. This session
converted nothing in wave 0 and did not read the child's diagnoses before re-running. Fixtures were neither
restarted nor reseeded (`FIXTURE_META.INITIALIZED_AT = 2026-09-01 20:53:10.961888`, same as wave-0 report v1).

## 0. Wave-close brief (one page)

| Unit | PR / head attested | Merge state | Grade basis | LIVE confirmation this session | Verdict |
|---|---|---|---|---|---|
| **U0** `codes`, `tenants`, `plans` (Oracle `CODES`/`TENANTS`/`PLANS`) | PR #1423, branch `--u0` @ **`892eb88ac0c149ce8e5f67903e9e636aae4f485d`** | **Merged** into the run branch by `5ae78c3c` ("Merge PR #1423 (U0 reference)", parents `2b23785c` + `892eb88a`); head is an ancestor of the current run head `1c03cce7`; U0 code (`scripts/tp_mongo/load_u0.py`, `recon_report_u0.py`), the mapping/tolerance/canonicalization files and `.migration/recon/U0/*` are **byte-identical** between `892eb88a` and `1c03cce7` (`git diff --stat` empty) | **PASS carried** from the prior independent wave-0 report `tp-run/mongodb-20260901T205236Z--wave0-recon:.migration/recon/wave_reports/wave0.md` (commit `7c9b0d52`), which re-loaded the target from this exact head and graded it LIVE: gate PASS T1 3/3 · T2 14/14 · T3 104/104, probes 42/42 | Verbatim gate re-run LIVE against the current target: **PASS** T1 3/3 · T2 14/14 · T3 104/104, 0 findings, 0 warnings; `result.json` identical (modulo `generated_at`) to the prior report's gate and to the PR-committed `.migration/recon/U0/result.json`; target load state proven to be the prior session's post-reload state (see §2) | **PASS** |
| **Wave 0** | | | | | **PASS** |

- Per the wave brief, merged units are attested and carry the prior PASS instead of being re-graded; there are
  no unmerged units in wave 0, so the LIVE window was spent on a cheap confirmation (≈4 s of source time) that
  the carried verdict still holds against today's target state, rather than idle.
- **Nothing to fix.** No drift (source counts/hashes read twice, identical), no defect, no quarantine class
  declared or present for U0 (quarantine DB holds only U1/U2/U3 classes: `bad_csv_list`, `dirty_signup_dt`,
  `invoice_feed_orphan_lines`, `orphan_document_snapshots`).
- **Grading-only amendments: none warranted** (unchanged from report v1).
- **Cost (U0, serial):** source pre/post check 2 × 8 statements ≈ 0.5 s · gate 3.9 s (3 COUNT + 14 aggregate
  pairs + 3 keyed SELECT) · light probes ≈ 2 s (4 SELECT + 6 PL/SQL calls, one connection) ≈ 7 s of source time.

## 1. Attestation

- `git ls-remote origin tp-run/mongodb-20260901T205236Z--u0` → `892eb88ac0c149ce8e5f67903e9e636aae4f485d`
  (unchanged since report v1; PR #1423 head). `git merge-base --is-ancestor 892eb88a origin/<run>` → true.
- Loader last changed in `b14d3618` (before the head) and is unchanged at head and at run head; the load
  currently in the target was produced by the prior wave-0 session from this head (`load_head.log`, 22:49 UTC).

## 2. LIVE confirmation (verbatim harness, plugin `mongo-migration-plugin-6d021e15/0.2.1`)

```
recon run --unit U0 --family oracle --mapping wave0_part1_evidence/U0/mapping_u0_subset.json \
  --tolerances .migration/02_tolerances.json --canonicalization .migration/canonicalization.json --mode live \
  --source-dsn-secret OW_BILLING_FIXTURE_DSN --target-uri-secret MONGODB_ATLAS_URI \
  --target-db ow_tp_mongodb_205236 --seed 714559852 --param batch_no=85559852 --param source_ns=demo \
  --out wave0_part1_evidence/U0/gate
```
`mapping_u0_subset.json` = `03_mapping_spec.json` at `892eb88a` filtered to `unit == "U0"` (sha256 equal to
report v1's subset file). Result **PASS**, `full_diff` populations codes 32 / tenants 69 / plans 3.

Load-state proof: sorted relaxed-extended-JSON dumps of `tenants` and `plans` hash exactly to the
`pre_target_tenants.sha256` / `pre_target_plans.sha256` snapshots recorded by report v1 (which showed those two
collections reload byte-identically from the head); `codes` differs only by the auto `ObjectId _id` (as
documented in report v1 finding 2) and is value-equal 32/32 on `_key`/`code_type`/`code_val`/`code_desc`.
Collection UUIDs unchanged across the gate (no concurrent writer): codes `dd337aca…`, tenants `fa194e28…`,
plans `a37fb2e1…`; counts 32/69/3.

Drift triage: `CODES`=32, `TENANTS`=69, `PLANS`=3 and per-table `ORA_HASH` content hashes identical on two
passes bracketing the gate; `FIXTURE_META` timestamp unchanged → no drift.

## 3. Light adversarial probes (this session; full 42-probe set is in report v1) — all ok

| Probe | Result |
|---|---|
| Independent value diff codes (`_key` → type/val/desc via `TO_CHAR`), tenants (id/name/status_cd/tax_exempt_yn) | 0 missing / 0 extra / 0 diff |
| Plans numeric fields | value-equal: Oracle `49`/`.055` etc. vs Decimal128 `49.00`/`0.055000` — scale quantized to `NUMBER(12,2)`/`(12,6)` per spec (`ROUND_HALF_EVEN`), numerically exact; only my un-masked `TO_CHAR` differs textually |
| BSON types | `code_val`/`status_cd`/`tier_cd` int32, `included_units` Int64, fees/rates Decimal128, strings elsewhere — as spec |
| Field sets / `ns` | only declared fields + `ns` (+ auto `_id` on codes); `ns == "mongo_205236"` on 100 % |
| Duplicate keys | 0 on `codes._key`, `tenants._id`, `plans._id` |
| Indexes | `codes`: `_id_` + unique `code_type_1_code_val_1`; `tenants`/`plans`: `_id_` only — as spec |
| Quarantine classes as SETS | U0 expects {} ; U0-attributable classes present = {} ✔ |
| App replay `PKG_OW_UTIL.F_CODE_DESC` (5 codes + `INV_STATUS/9999`) vs Mongo unique-index lookup with `UNKNOWN(n)` fallback | 6/6 equal |
| Embeds | n/a (no embeds; nothing UNGRADED) |

## 4. Cross-unit consistency

Unchanged from report v1 §4 (tenants.status_cd ⊂ TENANT_STATUS, plans.tier_cd ⊂ PLAN_TIER,
SUBSCRIPTIONS→tenants/plans 100 %, `CUSTOMER_MASTER.TENANT_ID` 0/50 resolves in source too — source property,
carried into U1 and confirmed again by the wave-1 report as F-XU-1). Not re-executed here (U0 data unchanged).

## 5. Findings

1. No defects; no drift. Verdict PASS carried and independently confirmed LIVE.
2. Informational: the run-branch mapping is already **v1.0.1** (the codes `_key` grading-only amendment
   applied by the orchestrator in `40e7c54c`); the wave brief cites "mapping v1.0" — no action, noted for
   ledger consistency.

## 6. Grading-only amendments

None warranted.

Evidence: `wave0_part1_evidence/U0/{gate/{result.json,report.md,recon.summary.md},gate.log,
mapping_u0_subset.json,src_check.py,src_pass1.json,src_pass2.json,uuids_before_gate.txt,uuids_after_gate.txt,
probes_light.json}`. Prior full evidence: `tp-run/mongodb-20260901T205236Z--wave0-recon:.migration/recon/wave_reports/wave0_evidence/U0/`.
