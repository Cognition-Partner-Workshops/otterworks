# 08 — Cutover runbook (customer-executed)

Every production-touching step below is executed by the **customer cutover principal**.
Devin holds no production credential, does not hold the repoint principal, and does not
request it. Devin's own steps need only the migration principal it already used
(`MONGODB_ATLAS_URI`, SELECT-only Oracle).

Read §1 first: this repoint covers part of the estate deliberately.

## 1. Scope of this repoint — what moves and what does not

**Moves to `ow_tp_mongodb_orc1`:**

| Path | Today | After |
|---|---|---|
| Billing report read path (`services/legacy-billing/app/reports.py`, `/api/legacy/billing-report`, and the admin dashboard billing-report page it feeds) | `oracle_query()` against `OW_BILLING` | the migrated collections |
| Billing business logic — plans, rating, invoicing, dunning (5 packages / 19 routines) | PL/SQL in `OW_BILLING` | `.migration/stored_logic/billing_logic.py` over `MongoStore` |
| `TRG_SUB_NO_UNCANCEL` and the other 6 triggers | Oracle triggers | store-level guards, unique indexes, a TTL index |
| `JOB_PURGE_AUDIT_LOG` | `DBMS_SCHEDULER` | TTL index on `billing_audit_log.logged_at` |
| `JOB_NIGHTLY_DUNNING` | `DBMS_SCHEDULER` | `billing_logic.nightly_dunning()`, fired by the application scheduler |

**Still reads Oracle after this repoint** (unchanged, deliberately):

- The ksh/Perl batch chain and its file drops — not in this run's scope.
- `services/legacy-billing`'s Postgres-backed Flask routes: those are a different estate
  (`billing` schema in Postgres) and are untouched by this migration.
- Anything reading `FIXTURE_META`.

## 2. Pre-repoint checks (Devin, migration principal, at the window)

1. Re-run the watermark recon: `bash .migration/tools/watermark_recon.sh` — all 7 units
   must print PASS. Any FAIL cancels the window; it means the source moved.
2. Re-run stored-logic parity: `cd .migration/stored_logic && python mongo_record.py
   --target-db ow_tp_mongodb_orc1 --report-out ../recon/stored_logic/replay.json &&
   python mongo_parity.py` — must print 24/24.
3. Confirm Atlas headroom at the boundary and record it in `04_progress.md`.

## 3. Repoint (customer cutover principal)

1. **Announce the freeze.** From this point the legacy estate is read-only for the paths in
   §1. Nothing in this runbook makes Oracle read-only by itself; the customer enforces it
   (application config, or a `READ ONLY` grant change made by their DBA).
2. **Publish the connection string.** Put the Atlas URI in the deployment's secret store
   under the name the service reads; never in a config file, a log, or a PR.
3. **Flip the read path.** Point the billing report at the migrated collections and deploy.
4. **Flip the write path.** Enable the converted billing logic (plans, rating, invoicing,
   dunning) against `ow_tp_mongodb_orc1` and disable the PL/SQL entrypoints, so exactly one
   of them can write.
5. **Hand the scheduler over.** Disable `JOB_NIGHTLY_DUNNING` in Oracle and enable the
   application-side nightly call in the same change, so the night's dunning runs once.

**Point of no return: step 4.** Once the converted logic accepts a write, rolling back means
reconciling MongoDB writes back into Oracle by hand. Steps 1–3 are reversible by redeploying
the previous configuration.

## 4. Post-cutover verification (Devin, immediately after step 5)

1. `bash .migration/tools/watermark_recon.sh` — first-cycle recon against the now-frozen
   source; all 7 units PASS.
2. Billing report for a known tenant, old path vs new path: same rows, same totals.
3. Issue one invoice through the converted logic in a scratch tenant and check the invoice,
   its lines, its totals and the credit burn-down all committed together.
4. Next morning: confirm the nightly dunning ran exactly once (`dunning_attempts` has one
   new attempt per overdue invoice, not two).
5. Publish the result to the agreed channel and record it in `05_decisions.md`.

## 5. Rollback

**Trigger condition (customer confirms at STOP C):** any of — a failing recon in step 4.1, a
billing report mismatch in 4.2, or a P1 incident on a repointed path — within the first
**72 hours**.

**Procedure, rehearsed before the window rather than written down only:**

1. Redeploy the previous configuration (read path and business logic back to Oracle) — one
   deployment, no data movement, valid while no MongoDB write has landed.
2. Re-enable `JOB_NIGHTLY_DUNNING`.
3. Lift the read-only freeze on the estate.
4. If MongoDB writes did land (past the point of no return), stop and reconcile: export the
   documents written after the watermark and replay them into Oracle under the customer's
   change process. This is why the trigger condition is checked at step 4.1, before traffic.

Rehearsal: steps 1–3 are executed against a non-production tenant during the window
preparation and the result recorded, so the rollback is a tested procedure at STOP C.

## 6. Decommission plan

| When | What | Who |
|---|---|---|
| Cutover + 72 h | Rollback window closes; rollback rehearsal artifacts archived | customer |
| Cutover + 72 h | Oracle estate stays **read-only** for the agreed retention window | customer DBA |
| Retention end (proposed: 90 days) | `OW_BILLING` retired; final export archived per the customer's retention policy | customer |
| Retention end | Legacy PL/SQL, triggers and jobs dropped (already disabled at cutover) | customer DBA |
| Cutover + 72 h | **Devin's migration access revoked**: the Atlas migration principal and the Oracle SELECT account used this run | customer |

Devin's own access revocation is part of the plan, not an afterthought: after the
post-cutover verification in §4 there is no remaining task that needs either credential.
