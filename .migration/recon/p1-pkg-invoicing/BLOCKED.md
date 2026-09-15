# p1-pkg-invoicing (U-23, wave 3 / batch w3-b) — HALTED

**status=BLOCKED, control=`undeclared_write_target`. No conversion was written, no recon was
run, no PR was opened.** There is no verdict for this unit, degraded or otherwise.

## Declared scope for this unit

Write targets: `billing.invoices`, `billing.invoice_lines`, `billing.sp_issue_invoice`,
`billing.fn_invoice_preview`, `billing.fn_invoice_lines`.
Runtime writes into another unit's tables: `billing.credit_notes` only.

## What the source writes that is not in that list

`services/legacy-billing/db/oracle/packages/04_pkg_invoicing.sql`, in `sp_issue_invoice`:

1. **`billing.billing_audit_log`**, via the logging call at the end of the procedure (:192):

   ```sql
   pkg_ow_util.log_msg('INVOICING', 'issued invoice=' || v_invoice_id ||
       ' total=' || TO_CHAR(NVL(v_total, 0)));
   ```

   The converted `billing.log_msg` already on the wave branch
   (`databricks/migration/lakebase/w0a_pkg_ow_util.sql`) inserts into
   `billing.billing_audit_log`. That table is owned by wave 0 and is not a declared write
   target or runtime write for w3-b. This is the exact scope finding the wave-3 addendum
   says not to repeat: "a batch wrote `billing.billing_audit_log` at runtime through
   `log_msg` without declaring it".

2. **`rating_periods` and `rating_results`**, via `pkg_rating.sp_finalize_rating` at :134,
   which upserts both (`03_pkg_rating.sql:183-211`). Those objects belong to unit
   `p1-pkg-rating` in batch w3-a, running concurrently. The hand-off this batch was given is
   a **read** of `billing.rating_state`; finalisation is a write, and it is not in this
   batch's scope.

Both are transitive writes through calls the source makes, not writes this unit would add.

## Why this is a halt and not a routing problem

Every available route is a rule violation:

- Dropping the `log_msg` call would delete observable legacy behaviour (and the swallowed
  `WHEN OTHERS THEN NULL` inside it is itself declared behaviour under P1-D2).
- Redirecting the log elsewhere, or creating a new audit table, is a write outside
  `.migration/allowed_targets.json` scope and invents an object no analysis approved.
- Calling `billing.log_msg` anyway is the undeclared runtime write named above.
- Skipping `sp_finalize_rating` changes what the invoice totals are computed from; writing
  `rating_periods`/`rating_results` ourselves is another unit's object.

Naming it is the job. Resolution is a human scope decision, not a child-session one.

## What would unblock it

Either of these, recorded as a decision:

1. Add `billing.billing_audit_log` to this unit's declared runtime writes (DDL ownership
   stays with wave 0; this unit would issue the `INSERT` only through `billing.log_msg`),
   and add `rating_periods` / `rating_results` as runtime writes owned by w3-a — or
2. Re-scope U-23 to depend on w3-a's converted `sp_finalize_rating` and declare the
   finalisation call as a cross-unit runtime write.

Everything else for this unit is ready: the two tables it operates on
(`billing.invoices`, `billing.invoice_lines`) are migrated and reconciled by
`p1-invoices` and `p1-invoice-lines` in this same batch, `billing.credit_notes` and
`billing.rating_state` both exist on the wave branch with the pinned shape, and the
conversion decisions are settled (named `TAX_RATE` constant at 0.0825, `billing.rating_state`
read instead of package globals, plain `DELETE FROM billing.invoice_lines WHERE
invoice_id = ...` instead of `EXECUTE IMMEDIATE`, credit burn-down in `issued_on, id` order
with the running-counter quirk verbatim, both roundings kept).
