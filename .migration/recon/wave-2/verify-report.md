run_id: ticket-c31e85659f634f69b45026185783e05c
manifest_sha: 6f95cb27913a

# Wave 2 (Rating) — independent verification (plan step `s4.2.verify`, ticket BILMG-12)

The verifier migrated nothing in wave 2. Everything below was re-run in this session from the committed spec on the merged run branch; nothing is copied from the batch worker's evidence.

## Verdict

| batch | units | verdict | basis |
|---|---|---|---|
| `w2-b01` | `rating` | **PASS** | own live re-run `.migration/recon/wave-2/w2-b01/rating/result.json`: verdict PASS, mode `live`, target_class `migration_cluster`, `merge_eligible: true`, 0 warnings, 0 findings; probes past the gate clean; rules gate PASS; harness parity 8/8 on the local stack; own read-only replay 7/7 |

Wave verdict: **PASS**.

## Identity

| item | value |
|---|---|
| run branch | `tp-run/mongodb-1792003347` @ `1de998c86` (w2-b01 merged, PR #2043) |
| batch result graded | `.migration/recon/w2-b01.json` (worker evidence `.migration/recon/rating/result.json`, generated 2026-10-15T00:36:12Z) |
| plugin | mongo-migration-plugin `main` @ `d6d72e8` (recon harness 0.3.3, editable install in `/home/ubuntu/.venvs/recon`; the clone was fast-forwarded to that SHA before the run) |
| mapping | `v2`, sha256 `6567c33adeada1a45ce93ab4096f2efb484e410263346dd66ed68f149a6e6704` (= committed `.migration/mapping_spec.json`) |
| tolerances | `tol-v1`, sha256 `829cbb4d2de0d3cf5296d29622973d4bb11915382b0634ab88ad9f040ef5c9c2` (= committed `.migration/recon_tolerances.json`), source_concurrency 1 |
| axes | `source_access: live` (local PostgreSQL 16 fixture `billing_mig`, role `billing_ro`, session TimeZone `Etc/UTC`) × `target_access: migration_cluster` (Atlas `otterworks-demo`, db `billing_migration`) |
| manifest_sha | `6f95cb27913a` — reproduced with `preflight.py --wave` from the wave-2 spec fields (wave 2, w2-b01, units/write_targets/fixture_manifest/versions/sha256s from `.migration/units.json`) with `auto_merge: true`, as the ticket states; `auto_merge: false` gives `48c9d9691ea0` |
| secrets | `MONGODB_ATLAS_URI` (by name); `OW_BILLING_PG_RO_DSN` was not visible to this session, so the fixture was started with a session-local `BILLING_RO_PASSWORD` and `POSTGRESQL_RO_DSN` assembled in-shell (never written to disk or committed); see finding V1 |

## 1. Recon re-run (one live run, source concurrency 1)

Command (from the workspace root, branch `recon/wave-2`; `<plugin>` = the mongo-migration-plugin clone at `d6d72e8`):

```
recon run --unit rating --family postgresql --mapping .migration/mapping_spec.json \
  --collections ratingPeriods,usageEvents --tolerances .migration/recon_tolerances.json \
  --canonicalization <plugin>/skills/mongo-migration/profiles/postgresql.md --mode live --target-class migration_cluster \
  --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI --target-db billing_migration \
  --allowed-targets-file .migration/allowed_targets.json --source-concurrency 1 --seed 1 \
  --out .migration/recon/wave-2/w2-b01/rating/
```

Result (`w2-b01/rating/result.json`, generated 2026-10-15T00:50:32Z): **PASS**, `merge_eligible: true`, warnings `[]`, error `null`.

| tier | checks | result | detail |
|---|---|---|---|
| 1 counts_through_mapping | 5 | PASS | source ratingPeriods 3 / usageEvents 10; both declared indexes present |
| 2 per_field_aggregates | 7 | PASS | 4 fields deferred to tier 3 by rule (dates, the `kind` string), no finding |
| 3 keyed_diffs | 16 | PASS | full diff on both collections (3 / 10 keys, 0 duplicate source keys); embed `ratingPeriods.rating` value-graded, 3 subdocuments |

Source counts were identical in the harness run and in the probe runs a few minutes later (usage_events 10 / rating_periods 3 / rating_results 3): no drift observed, so the source side was not re-read a third time.

## 2. Probes past the gate (read-only; `evidence/probe.py` → `evidence/probes.json`)

| probe | usageEvents | ratingPeriods |
|---|---|---|
| docs vs rows | 10 / 10 | 3 / 3 |
| duplicate `_id` | 0 | 0 |
| natural key duplicates, both sides | n/a | (`tenantId`, `periodStart`) 0 / 0 |
| missing fields on target | none | none |
| explicit nulls on target (source NULLs) | 0 (0) | 0 (0) |
| BSON types (every doc) | `_id`, `tenantId` binData uuid subtype 4; `occurredAt` date; `units` int; `kind` string | `_id`, `tenantId` uuid 4; `periodStart`, `periodEnd` date |
| undeclared fields | none | none |
| exact value diff vs source (all fields, canonicalised) | 0 | 0 |
| docs not in source | 0 | 0 |
| indexes vs spec `collections[].indexes` | 1/1 (`tenantId`, `occurredAt`) | 1/1 unique (`tenantId`, `periodStart`) |
| `$jsonSchema` validator present, level strict | yes | yes |

Embed `ratingPeriods.rating` (1:1 subdocument of `rating_results`): 3 source child rows → 3 subdocuments, exactly one per period on both sides (0 periods without a rating, 0 ratings without a source result, 0 arrays where a subdocument is declared, 0 orphan child rows); 0 element value diffs over `id`, `subscriptionId`, `usedUnits`, `quotaUnits`, `rolloverUnits`, `billableUnits`, `overageAmount`, `createdAt`; element types uuid 4 / uuid 4 / int ×4 / decimal / date; no `periodId` copied into the subdocument and no undeclared subdocument field.

Boundaries (source = target): `periodStart` 2025-11-01..2026-01-01 and `periodEnd` 2025-11-30..2026-01-31, 0 periods with `periodEnd` before `periodStart`; `occurredAt` 2026-02-01T10:00Z..2026-02-28T10:00Z, `units` 1..2201, sum 4485; `kind` domain `{api, compute, storage}` with no leading/trailing spaces; `rating.overageAmount` 0..0 with scale ≤ 2, no negative integer field; `rolloverUnits = max(quotaUnits − usedUnits, 0)` and `createdAt = periodEnd` hold for 3/3 on both sides (the `sp_finalize_rating` invariants). Every target field mapped from a source DATE (`periodStart`, `periodEnd`: 6 values) is a BSON date at exactly 00:00:00.000 UTC; both TIMESTAMPTZ fields (`occurredAt` 10, `rating.createdAt` 3) are BSON dates whose millisecond-truncated multiset equals the source's (the source carries no sub-millisecond precision).

Period containment: joining usage events to rating periods the legacy way (`tenant_id` + `occurred_at::date BETWEEN period_start AND period_end`) gives 0 contained events per period on both sides (0 mismatches) — the seed has no usage inside any rated period (finding V5).

## 3. Cross-unit consistency

Wave-1 collections are unchanged in count (plans 3 / tenants 9 / subscriptions 9 on both sides). References from wave 2 into them: `usageEvents.tenantId` → tenants dangling 0 (source 0), `ratingPeriods.tenantId` → tenants dangling 0 (source 0), `rating.subscriptionId` → subscriptions dangling 0 (source 0), and every rating's subscription belongs to the period's tenant (0 cross-tenant on both sides). 9 tenants have usage and 1 tenant has rating periods on both sides.

Write fence: `billing_migration` holds exactly the five collections of waves 1 and 2 plus the empty `_connectivity_probe` already reported in wave 1 (finding V2); neither later-wave collection (`invoices`, `notifications`) exists, while the source still has invoices 3 / invoice_lines 2 / dunning_attempts 1 / notifications 1 rows — nothing outside the batch's scope was written.

## 4. Parity replay (`procs/scenarios/rating`)

- Fingerprints: recomputed `SOURCE_SHA 2b98f8dc…1929` and `FIXTURE_SHA 53b308f5…06da` equal `procs/transcripts/*_SHA`, every `RATING-00x` transcript and `evidence/procs_parity.json`, so the transcripts are current.
- Rules gate: `make procs-rules-gate MODULE=rating` → `Rules gate PASS: rating` (5 approved rules, 8 scenarios).
- Harness replay: `make procs-up NS=dev` + `make procs-parity NS=dev MODULE=rating` → `Parity PASS=8 FAIL=0 SKIP=0`, 0 contract errors (`evidence/procs_parity.{json,md}`). This ran against the disposable local compose stack (billing-service + `mongo:7` replica set, `target_class local`): it is parity evidence for the extracted code, **not merge evidence**; the stack was torn down afterwards and the Atlas database was never written by the verifier.
- Own read-only replay (`evidence/parity_replay.py` → `evidence/parity_replay.json`): RATING-001..006 (`fn_usage_rating`, tenants 7, 1, 2, 6, 8, 3 for 2026-02) and RATING-007 (`fn_usage_summary`, tenant 4) re-executed as one SELECT per function body under `billing_ro` on the live fixture (no EXECUTE) and as the equivalent reads on Atlas `billing_migration` with the arithmetic of `rating.sql` mirrored in the script (not the billing-service code). Every column the function returns is compared legacy vs target (`used_units`, `quota_units`, `rollover_units`, `billable_units`, `first_tier_units`, `second_tier_units`, `overage_amount`; `kind`, `event_count`, `units`), and the business-field subset the scenario pins is compared to the committed transcript: 7/7 equal on both comparisons, covering the rollover lookback (RATING-002: 200 units from three prior periods), the suspension proration (RATING-003: tenant 2 suspended 2026-02-15, billable 200 → 100, amount 8.74 → 4.37) and the 101-unit tier boundary (RATING-004/005/006). RATING-008 (`sp_finalize_rating`) is a write scenario and was exercised only through the harness replay above; neither the live fixture nor Atlas carries a 2026-02 period for tenant 1 (0 / 0), so the local replay did not leak into the live data.

## 5. Findings (none blocks the verdict)

- V1 — secret visibility (still open from wave 1): `OW_BILLING_PG_RO_DSN` is not injected into this worker session, so the fixture ran on a session-local `BILLING_RO_PASSWORD`; the verdict is unaffected because the role, grants and data are the committed fixture, but the org/repo secret scope is still not fixed.
- V2 — stray collection (still open from wave 1): `billing_migration._connectivity_probe` (0 documents) is still present; outside mapping spec v2 and every batch's write targets, untouched by the verifier; drop it under the write fence before cutover evidence.
- V3 — redaction salt (still open from wave 1): `RECON_REDACT_SALT` was unset for the batch run and this re-run (`redaction_salted: false`), so recon artifacts carry unsalted hashes of low-entropy values.
- V4 — imported identities: none of the 3 seeded `rating_periods` ids is `md5(tenant_id || period_start)` and none of the 3 `rating_results` ids is `md5(period_id)` (0/3 on both sides, source = target, so not a defect). Re-finalizing an imported period therefore has to match on (`tenantId`, `periodStart`) and on the existing subdocument, not on the derived id; RATING-008 exercises `sp_finalize_rating` only for a new period (tenant 1, 2026-02, fresh ids) on the local stack, so the re-finalize-an-imported-period path is covered by the batch's unit tests only, not by a recorded scenario.
- V5 — coverage limit of the seed: no usage event falls inside any seeded rating period (0 / 0), and every seeded result is the same shape (`usedUnits` 0, `quotaUnits` 100, `rolloverUnits` 100, `billableUnits` 0, `overageAmount` 0), so the stored `rating` subdocument exercises only the zero-usage/full-rollover path in live recon; the metering arithmetic (used units, tiers, proration, cents rounding) is proven live only through the function replays in §4.
- V6 — `occurred_at::date` is evaluated in the legacy session's time zone (`Etc/UTC` on the fixture) and the target computes the UTC calendar date; equal here (all events at 10:00Z), but a legacy client session in another zone would bucket events at day boundaries differently — pin UTC in the cutover runbook.
- V7 — `make tp-smoke` does not exist on the run branch (cut from `main`); CI's procs parity workflow stands in, as for the batch PR.

## Evidence on this branch

- `.migration/recon/wave-2/w2-b01/rating/{result.json,report.md,recon.summary.md}` — the verifier's live re-run (redacted)
- `.migration/recon/wave-2/verify-result.json` — the verify result JSON for `preflight.py --verify`
- `.migration/recon/wave-2/evidence/` — `probe.py`/`probes.json`, `parity_replay.py`/`parity_replay.json`, `procs_parity.{json,md}`
