# Migration run notes — schema `billing` → Atlas `billing_migration`

Human-readable notes that accompany the committed `.migration/*.json` contracts. One
section per plan step; the JSON files stay the machine-readable source of truth.

## s2.3 — dependency register (readers, writers, scheduled logic)

Scope: everything that reads or writes PostgreSQL schema `billing`, or runs on a schedule
against it. Confirmed on the live fixture (`billing_mig`, connected as `billing_ro`) and in
the repo at the s2.1 merge (`8dec13a65`). Dispositions: `migrate` (goes through a wave),
`keep-on-legacy-until-cutover` (repointed in p6), `out-of-scope` (with reason).

### Readers and writers

| # | Component | What it does to `billing` | Principal | Disposition |
|---|---|---|---|---|
| 1 | `services/legacy-billing/app/app.py` (Flask) | The only application client. 12 routes bind request values and call the 12 routines verbatim: `SELECT * FROM billing.fn_*` (7 functions) and `CALL billing.sp_*` (5 procedures), lines 56–146. No table-level SQL of its own. | `billing` = schema owner and, in the fixture, Postgres superuser (`docker-compose.procs.yml` → `DB_USER: billing`, `POSTGRES_USER: billing`) | `keep-on-legacy-until-cutover`. p6 repoints by replacing the data access in `app.py` (or retiring the app behind the migrated service); there is no repository layer to swap, so this is a code change, not a `DB_*` env change. |
| 2 | `procs/harness/record.py` (parity recorder) | Writer. `reset_database()` runs `DROP SCHEMA IF EXISTS billing CASCADE` then re-applies `DB_FILES` = `schema.sql`, `procs/{plans,rating,invoicing,dunning}.sql`, `seed.sql` (lines 26–32, 102–106) before every scenario, then calls the scenario entrypoint and runs state probes (direct `SELECT`s on `subscriptions`, `invoices`, `rating_results ⋈ rating_periods`, `credit_notes`, `dunning_attempts`, `notifications` — `procs/scenarios/*/*.yaml`). | `billing` (lines 40–47) | `out-of-scope`: parity oracle, stays on legacy by design. Manual only (`make procs-record`), refuses to overwrite transcripts. `billing_ro` survives the reset because `legacy_billing_ro.sql` sets database-wide default privileges (confirmed: `pg_default_acl` rows `billing_ro=U` on schemas, `billing_ro=r` on tables, `EXECUTE` revoked from PUBLIC on routines). |
| 3 | `procs/harness/replay.py`, `fingerprints.py`, `rules_gate.py`, `list.py` | No connection to `billing`. `replay.py` talks HTTP to billing-service (`/internal/reset`, module routes); `fingerprints.py`/`rules_gate.py` hash and parse the SQL source files. | — | `out-of-scope` (target-side / file-level). |
| 4 | `services/billing-service` (FastAPI) | Reads and writes its own schema `billing_svc` in a separate database `billing_svc_<NS>` (`app/config.py:6`, `app/db.py:29–31`, `docker-compose.procs.yml` `billing-service-db`). `scripts/generate_seed.py` regenerates `db/seed.sql` from the *text* of `services/legacy-billing/db/seed.sql` (tenants, plans, subscriptions) — a file dependency on the legacy seed, not a schema dependency. | `billing_svc` | `out-of-scope`: never connects to `billing`; it is the stored-procs-extraction demo target, not this migration's target. The seed coupling means a change to the legacy seed fails `test_domain.py`'s generated-seed test — relevant only if s2.4 ever edits `seed.sql` (it must not; legacy is read-only). |
| 5 | `frontend/client-app/src/features/billing/*` | `api.ts` calls `/billing-api/api/plans`, `/api/tenants/<id>/entitlement`, `/api/tenants/<id>/plan-change`; Vite proxies `/billing-api` to billing-service (`vite.config.ts:15–19`). | — | `out-of-scope`: reads only via the extracted service, never `billing`. |
| 6 | This run's reader: `.migration/fixtures/legacy_billing_source.sh` + `legacy_billing_ro.sql`, mongo-migration-plugin census / profile / access scan / recon | SELECT-only via `billing_ro`; the grant script runs once at fixture start as the owner, on the local fixture only. | `billing_ro` | `out-of-scope` (the migration's own read path; nothing to repoint). |

Nothing else in the repo connects to the legacy database: `scripts/` has no reference to
`billing.*` or the legacy DSN (`run-usage-rollup.sh` is analytics-service NDJSON);
`infrastructure/`, `platform/` and the Helm charts do not deploy `legacy-billing`;
`migration/job` (LDM) uses its own `ldm` Postgres on host port 55432 in CI — same port,
unrelated database.

### Table write map (who writes what, from `services/legacy-billing/db/procs/*.sql`)

| Table | Runtime writers | Notes |
|---|---|---|
| `tenants`, `plans`, `usage_events` | none — seeded only (`seed.sql`); `sp_suspend_overdue` updates `tenants.status` | `usage_events` is append-only input with no writer in the estate: static during the run. |
| `subscriptions` | `sp_change_plan` (INSERT, UPDATE), `sp_suspend_overdue` (UPDATE) | |
| `rating_periods`, `rating_results` | `sp_finalize_rating` (INSERT; `rating_results` upsert via `ON CONFLICT … UPDATE`) | |
| `invoices`, `invoice_lines`, `credit_notes` | `sp_issue_invoice` (INSERT invoice with `ON CONFLICT … UPDATE SET status='issued'`, DELETE+INSERT lines, UPDATE `credit_notes`, UPDATE `invoices`) | |
| `dunning_attempts`, `notifications` | `sp_schedule_dunning` (INSERT attempts), `sp_suspend_overdue` (INSERT notifications) | |

### Scheduled logic

- **Database side — none.** Live as `billing_ro` on `billing_mig`: 0 triggers, 0 event
  triggers, 0 rules, 0 views/materialized views, 0 sequences (uuid keys), extensions =
  `plpgsql` only, `pg_cron` not even available in the `postgres:16` image, 0 publications /
  subscriptions / foreign servers. Matches `census.json` (`triggers: []`,
  `scheduler_jobs: []`, `views: []`) and `schema.sql` (11 tables, no `CREATE TRIGGER` /
  `CREATE FUNCTION`).
- **Container side — none.** `docker-compose.procs.yml` has four services
  (`legacy-billing-db`, `legacy-billing`, `billing-service`, `billing-service-db`); no cron
  or sidecar. The only automatic writes are `docker-entrypoint-initdb.d` (schema, procs,
  seed) on an empty volume.
- **Repo side — none scheduled.** `.github/workflows/procs-parity.yml` runs on push/PR to
  the listed paths, against a throwaway `NS=ci` stack, and runs `procs-rules-gate` and
  `procs-parity` (HTTP to billing-service) — never `procs-record`. `Makefile` `procs-*`
  targets are manual. `ci.yml` does not reference the legacy database.
- **"Scheduling" in the domain is data, not a timer.** `sp_schedule_dunning(p_as_of)`
  inserts `dunning_attempts` rows with `scheduled_for` (weekend-rolled) and
  `status='scheduled'` (`dunning.sql:20–47`); nothing fires them. A caller must POST
  `/api/dunning/schedule` and later `/api/dunning/suspend` with an `as_of` date.
  Disposition `migrate`: the dunning wave carries the `as_of`-driven semantics; there is no
  job to repoint in p6.

### Access check (`billing_ro`, live)

SELECT on all 11 tables = true; INSERT/UPDATE/DELETE = false on every table; schema
`USAGE` true, `CREATE` false; EXECUTE on all 12 routines = false (owner `billing` keeps
it). No missing access — every census object is readable, and the reader cannot invoke
business logic, so Tier-4 app parity comes from the `procs/` transcripts recorded as the
owner, not from `billing_ro`. No other sessions on `billing_mig` while probing.

Seeded row counts observed (for s2.4, since `census.seed_rows` is empty and the profile
reports `row_estimate_missing`): tenants 9, plans 3, subscriptions 9, usage_events 10,
rating_periods 3, rating_results 3, invoices 3, invoice_lines 2, credit_notes 5,
dunning_attempts 1, notifications 1.

### Findings for the manager

1. Secret `OW_BILLING_PG_RO_DSN` is not visible to this session in any scope (org,
   personal, repo). The fixture was started with a session-local `BILLING_RO_PASSWORD`
   (nothing committed, nothing shared). Later live steps need the secret NAME contract
   re-checked before they are dispatched.
2. The run branch has no `tp-smoke` Make target (it was cut from `main`, not
   `tech-partnerships`); the pre-PR gate named in the step text cannot run here. This PR
   adds only this notes file.
3. The legacy app's principal is the schema owner / superuser. Cutover (p6) cannot be a
   credential-only repoint; it is an `app.py` data-layer change or app retirement.
