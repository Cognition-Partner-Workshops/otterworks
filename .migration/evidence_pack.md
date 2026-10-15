# Evidence pack — legacy billing (PostgreSQL schema `billing`) → Atlas `billing_migration`

Plan step `s6.1-evidence-pack` (phase `p6-cutover`). Assembled from the merged run branch
`tp-run/mongodb-1792003347` @ `756badbeb` (p4 waves and p5 parallel run merged). This file
links and cross-checks the evidence already committed on the branch; it adds no new runs and
makes no Atlas or legacy writes. Secrets are named, never valued.

**Bottom line.** All 4 units (12 routines, 11 tables → 7 collections) are migrated and
independently verified PASS on live × migration_cluster recon; the parallel run closed with a
3/3 green streak and app-level parity PASS=24 on every cycle. Nothing is repointed yet: all
12 legacy Flask routes still read PostgreSQL, by design, until the customer authorizes and
executes the repoint (`d-cutover-authorization` is still open). Open items that must be
closed or explicitly accepted before the repoint are in §6; none of them changes a verdict.

## 1. Identity

| item | value |
|---|---|
| run branch / head | `tp-run/mongodb-1792003347` @ `756badbeb` |
| mapping spec | `.migration/mapping_spec.json` **v2**, sha256 `6567c33adeada1a45ce93ab4096f2efb484e410263346dd66ed68f149a6e6704` (accepted s3.1, PR #2026; same sha in `units.json` and in every `result.json` graded below) |
| recon tolerances | `.migration/recon_tolerances.json` **tol-v1**, sha256 `829cbb4d2de0d3cf5296d29622973d4bb11915382b0634ab88ad9f040ef5c9c2` (strict: numeric tol 0, full diff, source_concurrency 1) |
| units | `.migration/units.json` (s3.3, PR #2034), sha256 `5bc94c78702123d88a60d5d5c36794e745f79e5c776ba41ff74c418e07f49034`: 4 units, 12 routines, 7 collections, 11 source tables, 3 waves, 4 batches |
| axes | `source_access: live` (PostgreSQL 16 fixture `billing_mig`, role `billing_ro`, SELECT-only, session TimeZone `Etc/UTC`) × `target_access: migration_cluster` (Atlas `otterworks-demo`, db `billing_migration`) — `.migration/connectivity.json`, probed 2026-10-14T19:03Z, `privilege_excess_accepted` |
| write fence | `.migration/allowed_targets.json` = `billing_migration` only; `.migration/authorizations.json` = `[]` (no legacy write ever authorized; none occurred) |
| source fixture | `.migration/fixtures/legacy_billing.json`: FIXTURE_SHA `53b308f5…406da`, SOURCE_SHA `2b98f8dc…1929`, 49 rows / 11 tables |
| secrets (names) | `OW_BILLING_PG_RO_DSN` → `POSTGRESQL_RO_DSN`; `MONGODB_ATLAS_URI` |
| plugin | mongo-migration-plugin `main` @ `d6d72e8` (recon harness 0.3.3) for every graded run |

## 2. Coverage: tables and routines → units → collections

11 tables, 12 routines, 7 collections. Every table and routine appears in exactly one unit;
every collection is loaded by exactly one batch (wave-preflight collision check OK, #2034).

| unit (wave / batch) | routines (12) | source tables (11) | collections / embeds (7) | batch PR | verify |
|---|---|---|---|---|---|
| `plans` (w1 / w1-b01) | `fn_list_plans`, `fn_entitlement`, `sp_change_plan` | `plans` 3, `tenants` 9, `credit_notes` 5, `subscriptions` 9 | `plans`, `tenants{creditNotes[]}`, `subscriptions` | #2036 | #2042 PASS |
| `rating` (w2 / w2-b01) | `fn_usage_rating`, `fn_usage_summary`, `sp_finalize_rating` | `usage_events` 10, `rating_periods` 3, `rating_results` 3 | `usageEvents`, `ratingPeriods{rating}` | #2043 | #2044 PASS |
| `invoicing` (w3 / w3-b01) | `fn_invoice_preview`, `fn_invoice_lines`, `sp_issue_invoice` | `invoices` 3, `invoice_lines` 2, `dunning_attempts` 1 | `invoices{invoiceLines[], dunningAttempts[]}` | #2055 | #2058 PASS |
| `dunning` (w3 / w3-b02) | `fn_overdue_accounts`, `sp_schedule_dunning`, `sp_suspend_overdue` | `notifications` 1 | `notifications` | #2056 | #2058 PASS |

Row counts are the fixture seed (`legacy_billing.json`). Cross-unit writes (4, `units.json
cross_unit_writes`) go through the owning repository API inside one transaction
(`sp_issue_invoice` → `ratingPeriods`, `tenants.creditNotes`; `sp_schedule_dunning` →
`invoices.dunningAttempts`; `sp_suspend_overdue` → `tenants`, `subscriptions`). Identity rule:
every procedure-created id is the legacy `md5(...)::uuid`, so strict recon and references line up.

## 3. Wave verification (independent verifier, own live re-runs)

| wave | ticket `run_id` | `manifest_sha` | units | verdict | recon `result.json` (PASS, `live` × `migration_cluster`, `merge_eligible: true`, 0 warnings) | report |
|---|---|---|---|---|---|---|
| 1 Plans | `ticket-e880077948ab4d4bb2b47ccbaa0c494c` | `bdfa1550d194` | w1-b01 | **PASS** | `.migration/recon/wave-1/w1-b01/plans/result.json` (2026-10-15T00:02:58Z; tiers 12/13/26 checks) | `.migration/recon/wave-1/verify-report.md` (#2042) |
| 2 Rating | `ticket-c31e85659f634f69b45026185783e05c` | `6f95cb27913a` | w2-b01 | **PASS** | `.migration/recon/wave-2/w2-b01/rating/result.json` (00:50:32Z; 5/7/16) | `.migration/recon/wave-2/verify-report.md` (#2044) |
| 3 Invoicing + Dunning | `ticket-e6d86904b1da4d4199c2cf96ce5cd566` | `399f5a4f0b82` | w3-b01, w3-b02 | **PASS** | `.migration/recon/wave-3/w3-b01/invoicing/result.json` (01:52:05Z; 5/7/6), `.migration/recon/wave-3/w3-b02/dunning/result.json` (01:52:07Z; 2/3/1) | `.migration/recon/wave-3/verify-report.md` (#2058) |

Each `manifest_sha` was reproduced by the verifier from `units.json` with `auto_merge: true`
(wave-1 finding V4: `d-auto-merge` is false; merging stayed manual, the hash is a grading key only).
Each report also carries read-only probes past the gate, cross-unit consistency, and a parity replay
against the recorded transcripts (wave 1: 5/5; wave 2: 7/7 reads; wave 3: 3/3 + 1/1 reads and a
write-path replay of `sp_issue_invoice` ×3, `sp_schedule_dunning` ×3, `sp_suspend_overdue` ×2 on a
disposable stack). Batch gradings: `.migration/recon/w{1,2,3}-b01.json`, `w3-b02.json`.

## 4. Parallel run (p5): delta sync, continuous recon, app-level parity

Evidence root `.migration/recon/parallel-run/` (README.md; s5.1 #2059, s5.2 #2060). Mechanism:
`services/billing-service/app/delta.py` keyed diff (no watermark column exists in the legacy
schema), `cycle.py` replays all 10 procedure scenarios over HTTP with dates shifted N-1 months,
`run_cycle.sh N` = replay → `make procs-parity` → delta → `recon --mode continuous` (7 collections).

| cycle | parity (`s5.2/cycle-N/parity/parity.json`) | delta applied | continuous recon (`s5.2/cycle-N/recon/result.json`) |
|---|---|---|---|
| 1 | PASS=24 FAIL=0 SKIP=0 | tenants +3 / subscriptions +5 / ratingPeriods +4 / invoices +5 / notifications +1 | PASS, 136 checks, 0 findings |
| 2 | PASS=24 FAIL=0 SKIP=0 | tenants +3 / subscriptions +7 / ratingPeriods +8 / invoices +8 / notifications +1 | PASS, 168 checks, 0 findings |
| 3 | PASS=24 FAIL=0 SKIP=0 | tenants +3 / subscriptions +9 / ratingPeriods +12 / invoices +11 / notifications +1 | PASS, 200 checks, 0 findings |

Green streak **3/3** (`d-green-streak` = 3), red runs none — drift report `s5.2/drift.md`.
Idempotency: `cycle-3/delta-rerun.json` and `s5.2/restore-baseline/delta-rerun.json` are no-ops.
Atlas was re-synced from the `billing_mig` fixture after the cycles (`s5.2/restore-baseline/
delta.json`), so `billing_migration` matches the `billing_ro` source again. `merge_eligible` is
`false` in every continuous `result.json` by design (coexistence evidence, not merge evidence).

## 5. Procs parity report (merge authority, app level)

`.migration/recon/parallel-run/s5.2/cycle-3/parity/parity.{json,md}`: **PASS=24 FAIL=0
SKIP=0**, `contract_errors: []`, `target_class: migration_cluster` (billing-service on Atlas
`billing_migration`). Scenarios: plans 5 (PLANS-001..005), rating 8 (RATING-001..008), invoicing 6
(INVOICE-001..006), dunning 5 (DUNNING-001..005); every one of the 12 routines has at least one
scenario (`procs/scenarios/*/*.yaml`). `fixture_sha` and `source_sha` in the report equal the
fixture manifest's FIXTURE_SHA / SOURCE_SHA, so the transcripts graded are the ones recorded for
this seed and these procedure sources. Rules gate: `procs/rules/{plans,rating,invoicing,dunning}.
rules.yaml`, each `decision.status: approved`, reviewer dhrov.subramanian. CI
`.github/workflows/procs-parity.yml` runs the same gate on every PR to the run branch.

## 6. Open issues and dispositions

Status: **open** = must be closed before the repoint; **runbook** = carried into the cutover
runbook (s6.4) as a step or check; **accepted** = residual risk recorded, no action; **estate owner**
= legacy data fact, out of the migration's hands (legacy is read-only).

| # | issue (first seen) | effect on evidence | disposition |
|---|---|---|---|
| 1 | `OW_BILLING_PG_RO_DSN` not injected into any worker session (blocker `b-pg-ro-secret`, s2.3; waves 1–3 V1; s5.x) | none on verdicts: every run used the same `billing_ro` SELECT-only role via a session-local `BILLING_RO_PASSWORD`, never written to the repo | **open** — the catch-up recon at the freeze (s6.2) and the audit must run from the named secret, not a session-local password; fix the secret injection first |
| 2 | `RECON_REDACT_SALT` unset (waves 1–3 V3; s5.x) | `redaction_salted: false` in every `result.json` / `delta.json`: changed-key hashes are unsalted | **open** — set the engagement salt before any artifact leaves the repo; re-salting is not needed for the verdicts |
| 3 | `billing_migration._connectivity_probe`, 0 documents, left by the s1.2 probe (waves 1–3 V2; s5.x) | outside the mapping spec and every write target; shows up in collection listings | **runbook** — drop it under the write fence (`billing_migration` is allowlisted) as a pre-repoint step; this ticket is docs-only and did not touch it |
| 4 | no `make tp-smoke` target on the run branch (cut from `main`; s2.3 onward) | the pre-PR gate named in every ticket could not run | **accepted** — CI procs parity + billing-service `pytest` (55 passed) and `ruff` stood in on every PR; not a cutover item |
| 5 | wave-1 V4: `manifest_sha` reproduces only with `auto_merge: true` while `d-auto-merge` is false | grading-key mismatch only | **accepted** — merging stayed manual on every wave; the hashes in §3 are the ones the manager graded |
| 6 | wave-1 V5: seed has no subscription with `ends_on` set | `endsOn` exercised only on the NULL/missing path in live recon | **accepted** — `sp_change_plan` scenarios (PLANS-004/005) set `endsOn` on the migrated side and pass parity |
| 7 | wave-2 V4 / wave-3 V4: no seeded `rating_periods`, `rating_results`, `invoices`, `invoice_lines`, `dunning_attempts`, `notifications` id is the md5-derived identity (same on both sides) | re-finalizing an imported period or re-issuing an imported invoice's period follows a path no recorded scenario covers; billing-service matches imported rows on existence (`(tenantId, periodStart)`, unique keys), fixed in w2-b01 review | **accepted, audit item** — the independent audit (s6.3) should replay one re-finalize and one re-issue against an imported row; the legacy itself creates a second invoice on re-issue (wave-3 V4), so behaviour is already equal |
| 8 | wave-2 V5: no seeded usage event falls inside a seeded rating period; every seeded `overageAmount` is 0 | the stored `rating` subdocument exercises only the zero/rollover path live | **accepted** — metering arithmetic is proven by RATING-001..007 replays (7/7) and parity 24/24; post-cutover verification should read one real rated period |
| 9 | wave-2 V6: `occurred_at::date` follows the legacy session time zone; the fixture is `Etc/UTC`, the target buckets by UTC date | equal here; would diverge on a non-UTC legacy session | **runbook** — pin `TimeZone=UTC` on the repointed app's remaining legacy sessions (if any) and record the production legacy `TimeZone` before the freeze |
| 10 | wave-3 V5: all 3 seeded invoices reference another tenant's rating period and invoice `6000…01`'s lines do not reconcile to its subtotal/tax split | identical on both sides; migrated faithfully (legacy read-only) | **estate owner** — a data-quality fact of the legacy seed, not a migration defect; report, do not fix in flight |
| 11 | wave-3 V8: the dbx guard blocks a psycopg script that `CALL`s procedures on a disposable namespace's PostgreSQL (even rolled back) | the legacy side of the write-path replay is the committed `procs/transcripts/*` (recorded as the owner), not a live diff | **accepted** — parity 24/24 per cycle compares live billing-service results to those transcripts; guard blocks are findings, not routed around |
| 12 | wave-3 V6: live recon covers 1 `notifications` row and 1 `dunningAttempts` element | runtime write paths for dunning are proven on the disposable stack and by parity, not by Atlas data volume | **accepted** — demo-scale seed; s5.2 cycles added +1 notification per cycle on Atlas and reconciled PASS |
| 13 | wave-3 V9: local `mongo:7` WiredTiger fassert on the disposable stack, once | none (local fixture only) | **closed** |
| 14 | no `updated_at`/sequence column anywhere in legacy (s5.1) | incremental sync is a full keyed diff; a watermark would be a legacy schema change (forbidden) | **runbook** — the final catch-up at the freeze is one `python -m app.delta` keyed diff against `billing_migration`, then the full recon gate at that exact state (s6.2) |
| 15 | this pack: `wave-3/verify-result.json` lacks the `run_id`, `manifest_sha`, `wave` keys that waves 1 and 2 carry (the values are in the report's front matter) | machine readers of the wave-3 result miss two identity fields | **accepted** — recorded here from the report; the manager graded wave 3 with `--run-id` on that report |
| 16 | this pack: the legacy Flask app exposes no route for `fn_usage_summary` (`services/legacy-billing/README.md` lists it under Rating; `app/app.py` has none), and `GET /health` runs `SELECT 1` on legacy | one routine is reachable only through SQL/the extracted service | **accepted** — the routine is migrated (`GET /api/tenants/{id}/usage-summary`, RATING-007 parity PASS); the repoint table in §7 lists 12 Flask routes, not 12 routines |

Plugin gaps noted along the way (filed against mongo-migration-plugin, not hand-patched here):
postgresql census returns no CHECK constraints; postgresql family classifies `text` as LOB and
attaches `int_to_bool` to native booleans (fixed upstream in PRs #70, #71, used from `d6d72e8`).

## 7. Business-logic track: what repoints, what still reads legacy

Today (pre-authorization) **0 of 12** legacy Flask routes are repointed; **all 12 still read
PostgreSQL** through the schema-owner principal `billing`. The Flask principal is the schema
owner (and in the fixture the Postgres superuser), so the repoint cannot be a credential or `DB_*`
swap: it is an `app.py` data-layer change (each route calls `services/billing-service` over HTTP
or the app is retired behind it) — s2.3 finding 3. The customer executes it under
`d-cutover-authorization`; Devin never holds the cutover principal.

| legacy Flask route (`services/legacy-billing/app/app.py`) | routine | billing-service route (`procs/routes.yaml`, `services/billing-service/app/main.py`) | after repoint |
|---|---|---|---|
| `GET /`, `GET /plans` | `fn_list_plans` | `GET /api/plans` | repoint |
| `GET /plans/<tenant_id>/entitlement?on=` | `fn_entitlement` | `GET /api/tenants/{tenant_id}/entitlement?on=` | repoint |
| `POST /plans/<tenant_id>/change` | `sp_change_plan` | `POST /api/tenants/{tenant_id}/plan-change` | repoint |
| `POST /api/rating/preview` | `fn_usage_rating` | `GET /api/tenants/{tenant_id}/rating` | repoint |
| — (no legacy route) | `fn_usage_summary` | `GET /api/tenants/{tenant_id}/usage-summary` | migrated; nothing to repoint |
| `POST /api/rating/finalize` | `sp_finalize_rating` | `POST /api/tenants/{tenant_id}/rating-periods` | repoint |
| `GET /api/invoices/<tenant_id>/preview` | `fn_invoice_preview` | `GET /api/tenants/{tenant_id}/invoice-preview` | repoint |
| `POST /api/invoices/<tenant_id>/issue` | `sp_issue_invoice` | `POST /api/tenants/{tenant_id}/invoices` | repoint |
| `GET /api/invoices/<invoice_id>/lines` | `fn_invoice_lines` | `GET /api/invoices/{invoice_id}/lines` | repoint |
| `GET /api/dunning/overdue?as_of=` | `fn_overdue_accounts` | `GET /api/dunning/overdue-accounts?as_of=` | repoint |
| `POST /api/dunning/schedule` | `sp_schedule_dunning` | `POST /api/dunning/schedule-runs` | repoint |
| `POST /api/dunning/suspend` | `sp_suspend_overdue` | `POST /api/dunning/suspension-runs` | repoint |
| `GET /health` (`SELECT 1`) | — | `GET /health` (billing-service, reports its database) | repoint with the app |

Still reads legacy after the repoint, by design (s2.3 register): `procs/harness/record.py`
(the parity oracle; manual `make procs-record`, drops and re-creates the `billing` schema on a
disposable namespace only) and the migration's own `billing_ro` read path (`delta.py`, recon) until
the rollback window closes. `services/billing-service/scripts/generate_seed.py` depends on the
*text* of `services/legacy-billing/db/seed.sql`, not on the database. The web client
(`frontend/client-app/src/features/billing/*`) already talks to billing-service only.
No database-side or scheduled legacy logic exists to repoint (0 triggers, 0 jobs, 0 views).

A partial cutover (some routes repointed, others left on legacy) would be legitimate; it is
not the plan here because every route's routine is migrated and verified. If the customer
chooses to stage it, the per-route rows above are the units of that staging.

## 8. Pack check (this ticket)

Verified in this session, read-only, from the committed files:
- sha256 of `.migration/mapping_spec.json` and `.migration/recon_tolerances.json` recomputed and
  equal to `units.json` and to `mapping_sha256` / `tolerance_sha256` in all four wave `result.json`.
- Every wave `result.json`: `verdict PASS`, `mode live`, `target_class migration_cluster`,
  `merge_eligible true`. Every s5.2 `result.json`: `mode continuous`, 0 findings. Cycle-1..3
  `parity.json`: counts `{PASS: 24, FAIL: 0, SKIP: 0}`, `fixture_sha`/`source_sha` = fixture manifest.
- `run_id` / `manifest_sha` taken from each `verify-report.md` front matter (issue 15).
- 12 routine → 12 `routes.yaml` entrypoints → 24 scenarios → 13 Flask routes read directly from
  `app.py` (issue 16).

Not yet in the pack (later p6 tickets, per the cutover skill): the watermark/catch-up recon at
the freeze (s6.2), the countersigned independent audit (s6.3), the runbook with executor names
and rollback trigger (s6.4), the post-cutover recon and rollback drill (after the customer
executes). `make tp-smoke` does not exist on this branch (issue 4), so it did not run for this PR.
