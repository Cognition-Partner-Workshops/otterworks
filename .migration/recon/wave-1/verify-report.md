run_id: ticket-e880077948ab4d4bb2b47ccbaa0c494c
manifest_sha: bdfa1550d194

# Wave 1 (Plans) — independent verification (plan step `s4.1.verify`, ticket BILMG-9)

The verifier migrated nothing in wave 1. Everything below was re-run in this session from the committed spec on the merged run branch; nothing is copied from the batch worker's evidence.

## Verdict

| batch | units | verdict | basis |
|---|---|---|---|
| `w1-b01` | `plans` | **PASS** | own live re-run `.migration/recon/wave-1/w1-b01/plans/result.json`: verdict PASS, mode `live`, target_class `migration_cluster`, `merge_eligible: true`, 0 warnings, 0 findings; probes past the gate clean; parity replay 5/5 |

Wave verdict: **PASS**.

## Identity

| item | value |
|---|---|
| run branch | `tp-run/mongodb-1792003347` @ `4b6af777e` (w1-b01 merged, PR #2036) |
| batch result graded | `.migration/recon/w1-b01.json` (worker evidence `.migration/recon/plans/result.json`, generated 2026-10-14T23:52:09Z) |
| plugin | mongo-migration-plugin `main` @ `d6d72e8` (recon harness 0.3.3, editable install in `/home/ubuntu/.venvs/recon`) |
| mapping | `v2`, sha256 `6567c33adeada1a45ce93ab4096f2efb484e410263346dd66ed68f149a6e6704` (= committed `.migration/mapping_spec.json`) |
| tolerances | `tol-v1`, sha256 `829cbb4d2de0d3cf5296d29622973d4bb11915382b0634ab88ad9f040ef5c9c2` (= committed `.migration/recon_tolerances.json`), source_concurrency 1 |
| axes | `source_access: live` (local PostgreSQL 16 fixture `billing_mig`, role `billing_ro`) × `target_access: migration_cluster` (Atlas `otterworks-demo`, db `billing_migration`) |
| manifest_sha | `bdfa1550d194` — reproduced from the wave-1 spec fields (wave 1, w1-b01, units/write_targets/fixture_manifest/versions/sha256s from `.migration/units.json`) with `auto_merge: true`; see finding V4 |
| secrets | `MONGODB_ATLAS_URI` (by name); `OW_BILLING_PG_RO_DSN` was not visible to this session, so the fixture was started with a session-local `BILLING_RO_PASSWORD` and `POSTGRESQL_RO_DSN` assembled in-shell (never written to disk or committed); see finding V1 |

## 1. Recon re-run (one live run, source concurrency 1)

Command (from the workspace root, branch `recon/wave-1`):

```
recon run --unit plans --family postgresql --mapping .migration/mapping_spec.json \
  --collections plans,tenants,subscriptions --tolerances .migration/recon_tolerances.json \
  --canonicalization skills/mongo-migration/profiles/postgresql.md --mode live --target-class migration_cluster \
  --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db billing_migration \
  --allowed-targets-file .migration/allowed_targets.json --source-concurrency 1 --seed 1 \
  --out .migration/recon/wave-1/w1-b01/plans/
```

Result (`w1-b01/plans/result.json`, generated 2026-10-15T00:02:58Z): **PASS**, `merge_eligible: true`, warnings `[]`.

| tier | checks | result | detail |
|---|---|---|---|
| 1 counts_through_mapping | 12 | PASS | source plans 3 / subscriptions 9 / tenants 9; creditNotes 5 elements vs 5 child rows; all 8 declared indexes present |
| 2 per_field_aggregates | 13 | PASS | 10 fields deferred to tier 3 by rule (strings, booleans, dates), no finding |
| 3 keyed_diffs | 26 | PASS | full diff on every collection (3 / 9 / 9 keys, 0 duplicate source keys); embed `tenants.creditNotes` value-graded, 5 elements |

Source counts were identical in the harness run and in the probe run ~10 minutes later (3 / 9 / 9 / 5): no drift observed, so the source side was not re-read a third time.

## 2. Probes past the gate (read-only; `evidence/probe.py` → `evidence/probes.json`)

| probe | plans | tenants | subscriptions |
|---|---|---|---|
| docs vs rows | 3 / 3 | 9 / 9 | 9 / 9 |
| duplicate `_id` | 0 | 0 | 0 |
| natural key duplicates (code / name), both sides | 0 / 0 | 0 / 0 | n/a |
| missing fields on target | none | none | `endsOn` missing 9 (source `ends_on` NULL 9), `suspendedOn` missing 8 (source NULL 8) — `null_missing_equiv` honoured, no explicit nulls stored |
| explicit nulls on target | 0 | 0 | 0 |
| BSON types (every doc) | `_id` binData uuid subtype 4; decimal / int / bool / string as declared | `_id` uuid 4; bool / string | `_id`, `tenantId`, `planId` uuid 4; `startsOn` date (9), `suspendedOn` date (1) |
| undeclared fields | none | none | none |
| exact value diff vs source (all fields, canonicalised) | 0 | 0 | 0 |
| docs not in source | 0 | 0 | 0 |
| indexes vs spec `collections[].indexes` | 2/2, unique on `code` | 3/3, unique on `name` | 3/3 |
| `$jsonSchema` validator present, level strict | yes | yes | yes |

Embed `tenants.creditNotes`: 5 source child rows → 5 elements; length distribution {0: 6 tenants, 1: 1, 2: 2} equals the per-tenant source counts (0 mismatches, 0 orphan child rows, 0 element value diffs, 0 extra elements); elements typed uuid/date/decimal/decimal and sorted by (issuedOn, id).

Boundaries (source = target): `subscriptions.startsOn` 2026-01-01..2026-01-01, `suspendedOn` 2026-02-15 (1 row), `endsOn` none on either side; `plans.monthlyFee` 49..499, `overageRate` 0.02..0.055; `creditNotes.issuedOn` 2026-01-31..2026-02-02, `remainingAmount` 5..55; every target field mapped from a source DATE (`startsOn` 9, `suspendedOn` 1, `endsOn` 0, `creditNotes.issuedOn` 5 values) is a BSON date at exactly 00:00:00.000 UTC (0 non-midnight, 0 non-date); status domains `{active, suspended}` (tenants, subscriptions) and tiers `{starter, growth, scale}` inside the validators' enums; inactive plans 0 / 0; tax-exempt tenants 1 / 1.

Referential integrity: `subscriptions.tenantId` → tenants and `planId` → plans dangling 0 on target (0 on source); exactly one open subscription per tenant on both sides (9 tenants).

## 3. Cross-unit consistency

Wave 1 is the first wave, so there are no earlier-wave collections to reference. Write fence: `billing_migration` holds exactly the three declared write targets plus an empty `_connectivity_probe` collection (finding V2); none of the later-wave collections (`usageEvents`, `ratingPeriods`, `invoices`, `notifications`) exist yet, while the source still has 10 / 3 / 3 / 1 rows for them (plus rating_results 3, invoice_lines 2, dunning_attempts 1) — nothing outside the batch's scope was written.

## 4. Parity replay (`procs/scenarios/plans`)

- Fingerprints: recomputed `SOURCE_SHA 2b98f8dc…1929` and `FIXTURE_SHA 53b308f5…06da` equal `procs/transcripts/*_SHA` and every `PLANS-00x` transcript, so the transcripts are current.
- Rules gate: `make procs-rules-gate MODULE=plans` → `Rules gate PASS: plans` (4 approved rules, 5 scenarios).
- Harness replay: `make procs-up NS=dev` + `make procs-parity NS=dev MODULE=plans` → `Parity PASS=5 FAIL=0 SKIP=0` (`evidence/procs_parity.json`). This ran against the disposable local compose stack (billing-service + `mongo:7` replica set, `target_class local`): it is parity evidence for the extracted code, **not merge evidence**; the stack was torn down afterwards and the Atlas database was never written by the verifier.
- Own read-only replay (`evidence/parity_replay.py` → `evidence/parity_replay.json`): PLANS-001 (`fn_list_plans`), PLANS-002 and PLANS-003 (`fn_entitlement`, tenants 1 and 2 on 2026-02-28) re-executed as the functions' SELECT bodies under `billing_ro` on the live fixture and as the equivalent reads on Atlas `billing_migration`. Every column the function returns is compared legacy vs target (`fn_entitlement`: tenant_id, plan_code, tier, monthly_fee, included_units, subscription_status, effective_on; `fn_list_plans`: codes and fees in order), and the business-field subset the scenario pins is compared to the committed transcript; all equal for all three. PLANS-004/005 (`sp_change_plan`) are write scenarios and were exercised only through the harness replay above.

## 5. Findings (none blocks the verdict)

- V1 — secret visibility: `OW_BILLING_PG_RO_DSN` is not injected into this worker session (same as the batch worker reported), so the fixture ran on a session-local `BILLING_RO_PASSWORD`; the verdict is unaffected because the role, grants and data are the committed fixture, but the org/repo secret scope should be fixed before wave 2.
- V2 — stray collection: `billing_migration._connectivity_probe` (0 documents, `_id_` index only) was left by the s1.2 connectivity probe; it is outside mapping spec v2 and outside every batch's write targets. Not touched by the verifier; the manager should have it dropped under the write fence before cutover evidence is assembled.
- V3 — redaction salt: `RECON_REDACT_SALT` was unset for both the batch run and this re-run (`redaction_salted: false`), so recon artifacts carry unsalted hashes of low-entropy values; set the engagement-wide salt secret before wave 2.
- V4 — spec/decision mismatch: `manifest_sha bdfa1550d194` reproduces only with `auto_merge: true` in the wave-1 spec (`auto_merge: false` gives `b1586009d132`), while the plan decision `d-auto-merge` is `false`. Preflight accepts either under live × migration_cluster; the manager must grade with the spec that produced `bdfa1550d194` and keep merging manual as decided.
- V5 — coverage limit of the seed: no subscription has `ends_on` set, so the `endsOn` field and the `ends_on >= on` branch of `fn_entitlement` are exercised only by the missing/NULL path in live recon; the populated path is covered only by PLANS-004/005 in the local parity stack.
- V6 — guard interaction: the org dbx guard refused the first probe script (SQL built by string concatenation, connection kwargs without a literal); the script was rewritten with literal statements and a read-only connection option (`default_transaction_read_only=on`) and then ran. No guard was bypassed and no write was attempted on either side.

## Evidence on this branch

- `.migration/recon/wave-1/w1-b01/plans/{result.json,report.md,recon.summary.md}` — the verifier's live re-run (redacted)
- `.migration/recon/wave-1/verify-result.json` — the verify result JSON for `preflight.py --verify`
- `.migration/recon/wave-1/evidence/` — `probe.py`/`probes.json`, `parity_replay.py`/`parity_replay.json`, `procs_parity.{json,md}`
