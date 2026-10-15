# Parallel run (s5.1): delta sync legacy PostgreSQL → Atlas `billing_migration`

Coexistence-window evidence for the incremental load path. Written by the s5.1 ticket; refreshed
by every cycle. No secret values: sources and targets are named by secret NAME, changed keys are
logged as truncated SHA-256 hashes.

## Mechanism

- `services/billing-service/app/delta.py` (`python -m app.delta`): reads every source table once
  through `app.load.read_source` (one `billing_ro` connection, `REPEATABLE READ READ ONLY`,
  concurrency 1), maps rows through the same `build_documents` as the wave loaders (mapping spec
  v2, embedded `creditNotes` / `rating` / `invoiceLines` / `dunningAttempts` rebuilt with their
  parent), compares each document with the target by `_id` on its canonical BSON encoding, and
  applies the difference idempotently: `ReplaceOne(upsert=True)` for new or changed documents,
  `delete_many` for keys that left the source. Running it twice in a row is a no-op the second time.
  It refuses to run when a source table reads back empty while the target holds documents.
- **Watermarks: none available.** The census / `services/legacy-billing/db/schema.sql` show no
  `updated_at`, version or sequence column on any of the 11 billing tables; `rating_results.created_at`
  is set once and not touched by the `ON CONFLICT ... DO UPDATE` in `sp_finalize_rating`, so it cannot
  mark changes. Every collection therefore uses the keyed-diff fallback (`"watermark": null,
  "method": "keyed_diff"` in each `delta.json`). At demo scale (≤ 15 documents per collection) a
  full keyed diff costs one read per table; a watermark column would be a legacy schema change,
  which is out of scope (`authorizations.json` is `[]`).
- Writes go only to Atlas database `billing_migration` (`.migration/allowed_targets.json`,
  `mongo_guard`). No guard block occurred.
- `cycle.py` replays every `procs/scenarios/**` `kind: procedure` scenario against the legacy Flask
  app of a disposable procs namespace over HTTP (routes in `services/legacy-billing/app/app.py`);
  it opens no database connection. Scenario `date` inputs are shifted by N-1 months in cycle N
  because the scenarios are date-anchored business events and `sp_change_plan` is not re-runnable
  on the same date (subscription id = `md5(tenant, plan, effective_on)`); cycle 2 with no shift
  failed with `UniqueViolation` on `subscriptions_pkey` (that attempt was discarded).
- `run_cycle.sh N` = replay → delta → `recon run --mode continuous` on all seven collections.

## Cycles (namespace `p5`, legacy app `127.0.0.1:8594`, source `billing_p5` via `billing_ro`)

Baseline before cycle 1: `baseline/delta.json` — 0 upserted, 0 deleted on all seven collections,
i.e. Atlas already matched the fixture seed from the merged waves.

| cycle | dates | scenarios replayed | delta applied | recon (continuous) | evidence |
|---|---|---|---|---|---|
| 1 | +0 mo | 10 (all ok) | tenants +3 / subscriptions +5 / ratingPeriods +4 / invoices +5 / notifications +1 | **PASS** (136 checks, tiers 1-3) | `cycle-1/cycle.json`, `cycle-1/delta.json`, `cycle-1/recon/result.json` |
| 2 | +1 mo | 10 (all ok) | tenants +2 / subscriptions +4 / ratingPeriods +4 / invoices +7 | **PASS** (172 checks, tiers 1-3) | `cycle-2/cycle.json`, `cycle-2/delta.json`, `cycle-2/recon/result.json` |
| 3 | +2 mo | 10 (all ok) | subscriptions +4 / ratingPeriods +4 / invoices +5 | **PASS** (204 checks, tiers 1-3) | `cycle-3/cycle.json`, `cycle-3/delta.json`, `cycle-3/recon/result.json` |

Idempotency: `cycle-3/delta-rerun.json` — the sync re-run with no new cycle applied
0 upserts / 0 deletes (66 unchanged).

Three consecutive green cycles: **3 / 3** (acceptance met). `merge_eligible` is `false` in every
`result.json` by design: the harness grants it only to `live`/`snapshot` runs; `continuous` runs are
coexistence evidence, not merge evidence.

## Restore to the source fixture

The cycles ran on the disposable namespace, so Atlas was re-synced from the committed source
fixture `billing_mig` (`NS=mig`, port 55433) afterwards: `restore-baseline/delta.json` —
tenants +3 -0 / subscriptions +3 -6 / ratingPeriods +0 -12 / invoices +2 -9 / notifications +0 -1; `restore-baseline/delta-rerun.json` is a no-op. Namespace `p5` was torn down
(`docker compose down -v`). Atlas `billing_migration` therefore matches the `billing_ro` fixture
again for s5.2.

## Drift report

| finding | class | disposition |
|---|---|---|
| No `updated_at`/sequence columns anywhere in the legacy schema | source limitation | keyed diff on all collections; a watermark would need a legacy schema change (forbidden) |
| `OW_BILLING_PG_RO_DSN` not injected in the worker environment | environment | session-local `BILLING_RO_PASSWORD` → `POSTGRESQL_RO_DSN` built in one-shot shells, never written to disk in the repo |
| `RECON_REDACT_SALT` unset | environment | harness warns; `redaction_salted: false` in every `delta.json` / `result.json`; set the engagement salt before sharing artifacts |
| `procs/scenarios` not re-runnable on the same dates | fixture | cycle N shifts date inputs by N-1 months (recorded as `date_inputs_shifted_months`) |
| `make tp-smoke` absent on the run branch | repository | billing-service `pytest` (54 passed) and `ruff` run instead |
| `_connectivity_probe` (empty, stray) | carry-over | untouched; cutover item |

No data drift: every cycle's recon passed on tiers 1-3 with zero findings.
