# 10 Cutover runbook — OtterWorks billing → Atlas

Every production step is run by the **customer executor** with the customer-held cutover
principal. Devin holds no production credential and executes no step in §3–§5.

## 1. What repoints, and what does not

Read this first; it decides the shape of the window.

**Repoints to Atlas (read paths):**
- RPT-114 month-end finance report → `invoices` filtered `source: "conversion"`
  (`07_dependency_register.md` D2-2). Its numbers are unchanged: the 37 orphaned lines fall
  out of its join today and are out of `invoices` tomorrow.
- Any read-only consumer of customers, tenants, plans, codes, usage or credit notes.

**Stays on Oracle (write paths):**
- `billing-service` invoicing, rating and dunning. The five PL/SQL packages were not
  converted (D3-1) — nothing in Atlas implements that logic. `PKG_INVOICING`, `PKG_RATING`
  and `PKG_DUNNING` keep writing to Oracle until the stored-procs track lands.
- The CUSTBILL conversion feed, dormant today (D1-2).

So this is a **partial cutover**: reads move, writes do not. Hiding that would be worse than
saying it.

## 2. Preconditions (check, do not assume)

1. Watermark recon green for all five units: `recon/watermark/*.result.json`.
2. No source write since the watermark **2026-09-15T06:00:42Z**. Verify:
   `SELECT COUNT(*) FROM INVOICE_HEADER; SELECT COUNT(*) FROM CUSTOMER_MASTER;`
   → must be 18,750 and 25,000. Both scheduler jobs still `enabled=FALSE`.
3. Independent audit countersigned (`11_audit.md`).
4. STOP C authorization row in `05_decisions.md` naming the window, the executor and the
   rollback trigger.

If any source count moved, stop: re-run the affected unit's loader and its recon before
going on. A stale copy is a silent data-loss event.

## 3. Repoint (customer executor)

1. **Freeze.** Take the read consumers offline, or accept a stale read for the length of the
   window. The source is quiet, so no write freeze is needed — writes are staying on Oracle
   anyway.
2. **Final catch-up.** Run the five loaders once more from the migration host; they are
   idempotent and converge the target key set:
   `python3 migrations/mongodb/{reference/load_reference,customers/load_customers,invoices/load_invoices,usage/load_usage,ancillary/load_ancillary}.py`
   Expect the same counts as §5 of the evidence pack.
3. **Recon at that watermark.** `bash` the same five `recon run --mode live` invocations
   recorded in `recon/watermark/`. All five must print PASS. A FAIL here is a stop, not a
   note.
4. **Switch the read consumers' connection string** to the Atlas cluster, database
   `ow_billing_migration`, using the customer's own application principal (not the migration
   principal, which keeps write access it no longer needs). Config, DNS or feature flag —
   whichever the consumer uses.
5. **Leave Oracle up and writable.** It is still the system of record for billing writes.

## 4. Verification, immediately after (customer executor runs, Devin reads)

| Check | Expected |
|---|---|
| `db.customers.countDocuments({})` | 25,000 |
| `db.invoices.countDocuments({source:"conversion"})` | 18,750 |
| `db.invoices.countDocuments({source:"billing"})` | 3 |
| `db.invoice_lines_orphaned.countDocuments({})` | 37 |
| `db.tenants.countDocuments({})` | 69 |
| `db.invoices.aggregate([{$match:{source:"conversion"}},{$group:{_id:null,t:{$sum:{$toDecimal:"$totals.total"}}}}])` | `187618458.58`, equal to Oracle's `SUM(TOTAL_AMT)` on `INVOICE_HEADER` to 0.01 |
| RPT-114 run against Atlas for the last closed month | line-for-line equal to the Oracle run |

RPT-114 has no Atlas implementation yet: the report is Oracle SQL in
`services/legacy-billing/app/reports.py` and rewriting it against `invoices` is customer
work under D2-2. Either schedule that rewrite before the window or drop the row and accept
the count and sum checks as the verification — say which at STOP C.

The field is `totals.total` (Decimal128). There is no `totalAmount`; a query against that
name returns nothing and looks like a pass.

Then Devin runs the first-cycle recon and posts the result.

## 5. Rollback

- **Trigger (recommended):** any verification row in §4 unequal, or RPT-114 differing on any
  line, or a read consumer erroring on Atlas, within **24 hours** of the repoint.
- **Procedure:** set the read consumers' connection string back to Oracle. That is the whole
  rollback — Oracle was never modified, never taken read-only and never stopped, and the
  Atlas database is a copy no one writes to.
- **Point of no return:** there isn't one during the 24-hour window. It arrives only when
  the stored-procs track repoints *writes* off Oracle, which is a different change with its
  own approval.
- **Test the rollback, don't just read it:** flip one non-critical read consumer back to
  Oracle and confirm it serves, before the window closes.

## 6. Decommission (nothing before the rollback window closes)

1. Oracle `OW_BILLING` stays writable and authoritative — writes never left it.
2. After 24 hours with no rollback: revoke the migration principal's write access to
   `ow_billing_migration`; it exists only to load.
3. `ORACLE_BILLING_URI` and `MONGODB_ATLAS_URI` as held by Devin are revoked at the same
   time. Devin needs neither after post-cutover verification.
4. Legacy retirement is out of scope for this migration and waits on the stored-procs track.
