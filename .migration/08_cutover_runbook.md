# 08 — Cutover runbook (customer-executed production repoint)

Engagement: OW_BILLING Oracle → MongoDB Atlas (`ow_tp_mongodb_032752`), run branch
`tp-run/mongodb-20260901T032752Z`. Every production-touching step below is executed by the
**customer cutover executor** with the customer-held principal. Devin holds only the
migration principal and never executes the repoint.

## 1. Scope of this repoint — what it covers and what still reads legacy

Covered (repointed to MongoDB on cutover):
- Billing reports service (`services/legacy-billing`): invoice-feed status/line reports
  (U2), customer balance report (U1) — flag-gated Mongo backends already merged.
- Converted business-logic services (`scripts/tp_mongo/*_service.py`): plans/entitlement
  (U3, replaces PKG_PLANS), rating (U4, replaces PKG_RATING), invoicing (U5, replaces
  PKG_INVOICING), dunning (U6, replaces PKG_DUNNING + nightly job manual entrypoint),
  audit/util (U7, replaces PKG_OW_UTIL; audit purge replaced by TTL index).

Still reading the legacy system after this repoint (declared, not hidden):
- Nothing reads Oracle for serving after the flags below are set; Oracle remains up
  read-only for the rollback window and for reconciliation only.
- Declared-unexercised paths (see 04_progress.md "Unverified paths" per unit) remain
  unit-tested-only until first production traffic: trigger-replacement history writes
  (U1/U3, empty-at-source tables), UNKNOWN code branches (U2/U4/U6), transaction-rollback
  branches (U5/U6), U7 transforms over an empty audit log.

## 2. Preconditions (verified before STOP C was presented)

- All 8 units MERGED on independent recon PASS (wave reports 0/1/2/3a/3b in
  `.migration/recon/wave_reports/`).
- Final full recon at watermark SCN 3244576 green (`.migration/recon/cutover_watermark/`).
- 3 consecutive green parallel-run cycles (`.migration/recon/parallel_run/log.md`).
- Independent audit countersigned (`.migration/recon/audit/`, branch
  `recon/cutover-audit-20260901`).

## 3. Repoint steps (customer executor; customer-held principal)

1. **Freeze**: stop all writers to Oracle `OW_BILLING` (source has been read-only since
   seeding; confirm no writer was re-enabled). Record freeze time.
2. **Watermark check** (executor, read-only): confirm Oracle `CURRENT_SCN` row counts
   match `.migration/recon/cutover_watermark/watermark.json` (no drift since the final
   recon). Any drift → abort, notify Devin session for a delta catch-up.
3. **Repoint configuration** (per deployment of `legacy-billing` and the tp_mongo
   services), using the customer-held production Mongo principal:
   - `OW_BILLING_MONGO_URI=<customer production URI>` (never the Devin migration secret)
   - `OW_BILLING_MONGO_DB=ow_tp_mongodb_032752`
   - `MONGO_MIGRATION_DB=ow_tp_mongodb_032752`
   - `BILLING_BALANCES_BACKEND=mongodb`
   - `MONGODB_URI` for `scripts/tp_mongo/*_service.py` entrypoints, same value.
4. **Restart/rollout** the affected services.
5. **Verification queries (immediately after, executor)**:
   - `GET /reports/invoice-feed/status?ns=demo` returns `source: mongodb…` header and
     row totals matching the last Oracle-backed run (18,750 headers / 149,963 lines).
   - Balance report returns `source: mongodb` and grand total matching
     `.migration/recon/cutover_watermark/U1/` aggregates.
   - `subscriptions` count 69; `codes` 32; quarantine db untouched (37 orphan lines).
6. **Notify** the Devin session; Devin then runs post-cutover verification (first-cycle
   recon with the migration principal, read-only) and publishes the result.

## 4. Rollback procedure (tested as a procedure)

- **Trigger condition**: any verification query in step 5 mismatching, or any
  data-integrity error in the first agreed window (recommended: 24h) → roll back.
- **Procedure**: unset `BILLING_BALANCES_BACKEND` and `OW_BILLING_MONGO_URI` (the Oracle
  code paths are still present and were never removed), restart services. Oracle was
  frozen read-only at the watermark, so no backfill is needed within the window.
- **Point of no return**: the first write accepted by the Mongo stack that is not
  replayed to Oracle. The nightly dunning job and invoicing finalization are the first
  writers — do not enable them until the rollback window closes.

## 5. Decommission plan

- Oracle `OW_BILLING` stays up **read-only** for the agreed retention window
  (recommended: 30 days) for audit/reconciliation.
- After the window: retire the legacy schema per customer policy; archive the evidence
  pack (`.migration/`) with the run branch.
- **Principal revocation is part of the plan**: revoke Devin's migration principals
  (`MONGODB_ATLAS_URI`, Atlas API keys scoped to `otterworks-demos`, and the fixture
  Oracle credential) at window close; record revocation in `05_decisions.md`.
