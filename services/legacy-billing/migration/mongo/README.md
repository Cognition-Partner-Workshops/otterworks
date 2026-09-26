# Mongo migration service code — wave 3, batch w3-b02

Units: **u-09-plsql-rating** (PKG_RATING), **u-10-plsql-invoicing**
(PKG_INVOICING), **u-11-plsql-dunning** (PKG_DUNNING + JOB_NIGHTLY_DUNNING).

`target_class=local` — fixture evidence only, **not merge evidence**
(live recon: not possible; the engagement is offline,
`source_access=ddl_only`, `auto_merge=false`).

`ow_util.py` and `fixture_load.py` originate on branch
`...--w3-b01` (PR #1725); copied forward verbatim, with `fixture_load.py`
extended for this batch's collections and a `--scratch` flag.

## Files

- `rating_service.py` — PKG_RATING port: `compute_rating` (the g_* globals
  collapse into a result dict), `usage_rating` (fn_usage_rating),
  `usage_summary` (fn_usage_summary), `finalize_rating`
  (sp_finalize_rating upsert of ratingPeriods/ratingResults).
- `invoicing_service.py` — PKG_INVOICING port: `compute_preview`,
  `invoice_preview` (fixed 5-line preview), `invoice_lines` (embedded
  `invoices.lines`), `issue_invoice` (single-document invoice replace +
  oldest-first credit-note burn-down).
- `dunning_service.py` — PKG_DUNNING port: `overdue_accounts`
  (fn_overdue_accounts), `schedule_dunning` (sp_schedule_dunning with
  weekend push-out), `suspend_overdue` (sp_suspend_overdue with
  idempotent suspension notification + subscription hist writes).
  `run_nightly_dunning` is the JOB_NIGHTLY_DUNNING equivalent: a
  service entry point, **disabled by default** — nothing schedules it in
  this offline batch; wire a task runner at cutover.
- `fixture_load.py` — deterministic baseline loader: drops+recreates the
  spec collections these units read/write (`codes, plans, tenants,
  subscriptions, subscriptionsHist, billingAuditLog, usageEvents,
  ratingPeriods, ratingResults, invoices` (with embedded `lines`),
  `creditNotes, dunningAttempts, notifications`) plus the batch scratch.
- `parity_w3_b02.py` — replays `procs/oracle/transcripts/{rating,
  invoicing,dunning}/*.json` (19 transcripts) against the services with a
  baseline reset per scenario; verdict summaries into `parity_w3_b02`,
  transcripts under `recon/<unit>/parity/`.
- `ops/*.ops.json` — Tier-4 read-only op transcripts.
- `recon/<unit>/` — verbatim map-draft-3.1 subset specs + recon evidence.

## Usage (repo root, secrets by env-var NAME only)

    env -u MONGODB_ATLAS_URI \
      python3 services/legacy-billing/migration/mongo/fixture_load.py \
        --source-dsn-secret OW_BILLING_FIXTURE_DSN \
        --target-uri-secret MONGO_LOCAL_URI \
        --target-db ow_billing_migration --scratch parity_w3_b02

    env -u MONGODB_ATLAS_URI \
      python3 services/legacy-billing/migration/mongo/parity_w3_b02.py \
        --source-dsn-secret OW_BILLING_FIXTURE_DSN \
        --target-uri-secret MONGO_LOCAL_URI \
        --target-db ow_billing_migration
