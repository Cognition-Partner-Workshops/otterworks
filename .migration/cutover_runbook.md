# OtterWorks legacy billing: cutover runbook (PostgreSQL `billing` → Atlas `billing_migration`)

Plan step `s6.2-catch-up-recon`, phase `p6-cutover`. Written and verified by Devin; **executed by Dhrov
Subramanian** with the customer-held cutover principal. Nothing below has been executed: every Flask route
still reads PostgreSQL, `billing_migration._connectivity_probe` still exists, and no consumer is repointed.

**Who does what.** Dhrov executes sections 3–7 under decision `d-cutover-authorization` (open in `plan.yaml`).
Devin prepared the evidence (sections 1–2), writes nothing to the legacy estate ever
(`.migration/authorizations.json` is `[]`), does not hold or request the cutover principal or the schema-owner
`billing` password, does not run the repoint, the `_connectivity_probe` drop, or the rollback, and only
re-runs read-only recon when asked (section 6). A write blocked by `mongo_guard` or the committed
`.migration/allowed_targets.json` is a finding to report, never something to route around.

## 1. Evidence this runbook stands on

| gate | evidence | result |
|---|---|---|
| migration + verification of all 4 units / 12 routines | `.migration/evidence_pack.md` (#2061) | PASS on live × migration_cluster |
| parallel run | `.migration/recon/parallel-run/s5.2/drift.md` | 3/3 green cycles, parity 24/24 each |
| **freeze watermark** | `.migration/recon/freeze/watermark.json` | declared 2026-10-15T03:16:56Z: 49 rows / 11 tables, per-table sha256, source TimeZone `Etc/UTC` |
| **final delta at the watermark** | `.migration/recon/freeze/delta.json`, `delta-rerun.json` | keyed diff re-synced Atlas to the frozen source (1 `ratingPeriods` document left by the parity replay deleted, 0 upserts), re-run 0/0 (no-op), `redaction_salted: true` |
| **full recon gate at the watermark** | `.migration/recon/freeze/recon/result.json` | `verdict PASS`, `merge_eligible true`, mode `live`, `target_class migration_cluster`, mapping v2 `6567c33a…`, tolerances `tol-v1` `829cbb4d…`, tiers 1–3 103 checks, 0 findings |
| watermark held through the gate | `.migration/recon/freeze/watermark-check-{before,after}.json` | `freeze_held: true` both sides (table hashes unchanged; WAL LSN advances on an idle server and is context only) |
| app-level parity on Atlas | `.migration/recon/freeze/parity/parity.json` | PASS=24 FAIL=0 SKIP=0 against billing-service on `billing_migration` (fingerprinted via `/health`) |
| independent audit (session that migrated nothing) | `.migration/audit/countersign.md` | see file |

How to reproduce the freeze gate: `.migration/recon/freeze/run_freeze.sh` (header documents the inputs).

**Why "watermark" means a declared freeze and not a column.** The legacy schema has no `updated_at`,
version, or sequence column that is safe to read incrementally (`.migration/recon/parallel-run/README.md`),
so the s5.1 mechanism is a full keyed diff of every mapped table. The watermark is therefore an operational
declaration: the moment the customer stops legacy writes, recorded as per-table row counts + content hashes.
"At the watermark" is proven by the hash check passing before and after delta + recon, not by a timestamp.

## 2. Preconditions (check before authorizing; stop on any ✗)

1. **Legacy freeze.** All writers to PostgreSQL `billing` are stopped (legacy Flask app and the batch
   procedures). Re-declare the production watermark at that moment and check it right before step 4:
   `python .migration/recon/freeze/watermark.py --out <prod watermark.json>` then `--check`.
   (The committed `watermark.json` is the demo fixture's; production gets its own file.)
2. **`OW_BILLING_PG_RO_DSN`** exists as a named secret (role `billing_ro`, SELECT only, no EXECUTE) and is
   exported as `POSTGRESQL_RO_DSN` for delta and recon. Open issue from the evidence pack: it was **not
   injected** into any worker session so far; the freeze gate above ran from a session-local `billing_ro`
   password with the same grants. Before production: inject the named secret, then re-run step 4b with it.
3. **`RECON_REDACT_SALT`** exists as a named secret and is set wherever delta/recon run (artifacts carry
   `redaction_salted: true`). Open issue: it was unset in waves 1–3 and s5; the freeze gate ran with a
   session-local salt. Production artifacts must use the named secret.
4. **`MONGODB_ATLAS_URI`** (shared principal, `privilege_excess_accepted`, decided) reaches cluster
   `otterworks-demo`; the write fence is the committed `.migration/allowed_targets.json` = `billing_migration`.
5. **Legacy session time zone is UTC.** The fixture reports `Etc/UTC` (`watermark.json`,
   `session_timezone`). In production, verify on the schema-owner connection the Flask app actually uses:
   `SHOW TimeZone;` must return `UTC`/`Etc/UTC`; if not, pin it (`ALTER ROLE billing SET TimeZone = 'UTC'`
   or `options=-c TimeZone=UTC` in the app DSN) *before* the final delta, because `timestamp` columns are
   canonicalized as UTC in the mapping (`.migration/mapping_spec.json`) and a non-UTC session shifts the
   keyed diff. This is a customer action on the legacy estate; Devin does not run it.
6. **billing-service** is deployed with `BILLING_SVC_MONGODB_URI` → `MONGODB_ATLAS_URI`,
   `BILLING_SVC_MONGODB_DATABASE=billing_migration`, `BILLING_SVC_ALLOW_INTERNAL_RESET` **unset/false**, and
   `BILLING_SVC_SOURCE_DSN` **unset** (production never reloads from PostgreSQL). `GET /health` returns
   `database: billing_migration` and the cluster fingerprint `sha256(host)[:12]` of the Atlas URI.
7. `plan.yaml` decision `d-cutover-authorization` is approved by Dhrov in the Plan view.

## 3. Pre-repoint target hygiene (Dhrov, write fence only)

Drop the empty probe collection left by the s1.2 connectivity probe. It is outside the mapping spec and
every write target; `billing_migration` is allowlisted so this is inside the fence. Devin did **not** run it.

```
mongosh "$MONGODB_ATLAS_URI" --quiet --eval '
  const c = db.getSiblingDB("billing_migration")._connectivity_probe;
  if (c.countDocuments() !== 0) throw new Error("not empty, stop");
  c.drop();
  printjson(db.getSiblingDB("billing_migration").getCollectionNames());'
```

Expected: the 7 mapped collections only (`plans tenants subscriptions usageEvents ratingPeriods invoices
notifications`). Do not drop anything else.

## 4. Freeze, final delta, final gate (Dhrov; Devin may be asked to run 4b–4c read-only)

a. Stop legacy writers; declare the production watermark (precondition 1).
b. Final delta (keyed diff, idempotent):
   `cd services/billing-service && uv run python -m app.delta --source-dsn-secret POSTGRESQL_RO_DSN --target-uri-secret MONGODB_ATLAS_URI --log <out>/delta.json`
   then run it again: the second log must show 0 upserted / 0 deleted in every collection.
c. Full recon gate at exactly that state: the `recon run … --mode live --target-class migration_cluster`
   command in `run_freeze.sh`. Required: `verdict PASS`, `merge_eligible true`, mapping/tolerance sha256
   equal to section 1. Any other verdict: **do not repoint**; the legacy app keeps serving (nothing changed yet).
d. `watermark.py --check` passes again → the gate is at the watermark. Commit the three artifacts.

## 5. The repoint (Dhrov, with the customer-held principal)

**Why this is an `app.py` change and not a connection-string swap.** `services/legacy-billing/app/app.py`
opens PostgreSQL itself (`db_connect()` → `psycopg.connect`, `DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD`)
as role `billing`, the **schema owner** (and the fixture superuser), and every route runs SQL / `CALL`s a
stored procedure through `select()` / `execute()`. There is no repository layer to point at Mongo, and the
routines live in PostgreSQL. Repointing means replacing that data layer: each route becomes a call to
billing-service (or the client is cut over to billing-service directly and the Flask app retired). The
`billing` principal is customer-held; Devin never had it and does not need it.

Route map (legacy Flask → billing-service, routine it replaced):

| # | legacy route (`app.py`) | billing-service | routine |
|---|---|---|---|
| 1 | `GET /plans` (and `GET /` listing) | `GET /api/plans` | `fn_list_plans` |
| 2 | `GET /plans/<tenant_id>/entitlement?on=` | `GET /api/tenants/{tenant_id}/entitlement?on=` | `fn_entitlement` |
| 3 | `POST /plans/<tenant_id>/change` | `POST /api/tenants/{tenant_id}/plan-change` | `sp_change_plan` |
| 4 | `POST /api/rating/preview` | `GET /api/tenants/{tenant_id}/rating` | `fn_usage_rating` |
| 5 | `POST /api/rating/finalize` | `POST /api/tenants/{tenant_id}/rating-periods` | `sp_finalize_rating` |
| 6 | `GET /api/invoices/<tenant_id>/preview` | `GET /api/tenants/{tenant_id}/invoice-preview` | `fn_invoice_preview` |
| 7 | `POST /api/invoices/<tenant_id>/issue` | `POST /api/tenants/{tenant_id}/invoices` | `sp_issue_invoice` |
| 8 | `GET /api/invoices/<invoice_id>/lines` | `GET /api/invoices/{invoice_id}/lines` | `fn_invoice_lines` |
| 9 | `GET /api/dunning/overdue?as_of=` | `GET /api/dunning/overdue-accounts?as_of=` | `fn_overdue_accounts` |
| 10 | `POST /api/dunning/schedule` | `POST /api/dunning/schedule-runs` | `sp_schedule_dunning` |
| 11 | `POST /api/dunning/suspend` | `POST /api/dunning/suspension-runs` | `sp_suspend_overdue` |
| 12 | `GET /health` (`SELECT 1` on PostgreSQL) | `GET /health` (reports `database` + cluster fingerprint) | — |
| gap | *(no legacy route)* | `GET /api/tenants/{tenant_id}/usage-summary` | `fn_usage_summary` |

**`fn_usage_summary` gap.** The routine is migrated, parity-tested and exposed, but the legacy Flask app
never had a route for it (only PostgreSQL callers could reach it). There is nothing to repoint; decide
explicitly whether any consumer called it directly in PostgreSQL and point that consumer at the
billing-service route, or record it as "exposed, no legacy consumer".

Steps:
1. Branch from the run branch; change `app.py` so routes 1–12 call billing-service (`BILLING_SVC_URL`)
   instead of `select()`/`execute()`; remove `db_connect()` and the `DB_*` settings so the Flask process
   holds **no** PostgreSQL credential. Keep the external paths/shapes the client fixture already uses
   (`procs/routes.yaml` is the contract the 24 transcripts were recorded against).
2. Deploy with the `billing` DSN **removed** from the legacy app's environment. The schema-owner principal
   should no longer be present on any running consumer.
3. Smoke, in this order: `GET /health` on both services; route 1 (read), route 2 (read), route 6 (read),
   then one write, route 3 (`plan-change`) on a test tenant, and read it back with route 2.
4. First-cycle recon (section 6) within the first hour.

## 6. Post-cutover verification (Devin may run; read-only)

- `recon run … --mode live --target-class migration_cluster` against the frozen legacy source:
  must still PASS (the source is frozen, so any drift is on the target and means a consumer is writing
  unexpected shapes). Legacy writes after the freeze = rollback trigger (section 7).
- Parity harness replay is **not** run against production (it resets collections); it stays a
  pre-cutover gate (`.migration/recon/freeze/parity/`).
- `app.delta` is **not** run after the repoint: once consumers write to Atlas, a keyed diff from the frozen
  source would delete their writes. Retire it with the legacy writers.

## 7. Rollback (Dhrov)

**Point of no return:** the first write accepted by billing-service from a real consumer after the repoint
(step 5.2 live). Before it, rollback is a redeploy; after it, Atlas holds data PostgreSQL does not, and
rollback requires a reverse sync that does not exist in this plan — stop and decide instead of improvising.

Trigger (any one): `/health` red on billing-service or the repointed app; a smoke read in 5.3 differs from
the pre-cutover legacy answer; first-cycle recon not PASS; a legacy writer found still running
(watermark check fails); error rate or latency on routes 1–11 above the legacy baseline.

Steps:
1. Redeploy the previous `services/legacy-billing` image/revision (the one with `db_connect()`), restoring
   the `DB_*` environment with the `billing` principal; Dhrov supplies it, Devin does not.
2. Verify legacy `GET /health` and routes 1, 2, 6 answer from PostgreSQL. Resume legacy writers only if
   no Atlas write happened (point of no return above).
3. Leave `billing_migration` as is for diagnosis; do not drop or reload it. Record the trigger and the
   watermark check in `.migration/recon/freeze/` and reopen `d-cutover-authorization`.
4. Re-entry: the next attempt starts again at section 2 (new watermark, final delta, full gate).

## 8. What Devin does not do

Hold or request the cutover principal or the `billing` schema-owner password; change the legacy schema,
data, grants, routines or jobs (including `ALTER ROLE … SET TimeZone`); drop `_connectivity_probe`; edit
`app.py` or any consumer configuration in production; run the rollback; write to any database other than
`billing_migration`; treat a fixture PASS or `target_class: local` as merge evidence; or declare the
cutover done. Done is Dhrov's call on the evidence above.
