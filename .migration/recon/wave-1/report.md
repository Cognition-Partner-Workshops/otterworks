# Wave 1 reconciliation report (playbook 4, recon_mode: offline)

Verdict: fixture PASS, live recon pending customer run.

`merge_eligible=false` for every unit, reason: fixture evidence. The four unit PRs (#1652,
#1653, #1654, #1655) were merged into the work branch as the only merge target; nothing in
this wave makes any unit eligible for a production merge.

## What ran

1. Dropped local `ow_billing` (the only allowlisted target). `listDatabases` afterwards: admin,
   config, local.
2. Reloaded all four units independently from Oracle (read-only, `SET TRANSACTION READ ONLY`)
   with the merged loaders on the work branch: customers (3 collections), invoices (4),
   plans-rating (8), dunning (3).
3. Re-ran every unit's fixture recon from the spec (`--mode fixture`, map-1, tol-1, seed 1).
4. Diffed the rerun evidence against the evidence merged in the unit PRs (`pre/` vs `post/`).

## Per-unit verdicts

| unit | verdict | tier 1 counts | tier 2 aggregates | tier 3 rows | tier 4 app parity |
|---|---|---|---|---|---|
| w1-customers | PASS | 3 | 317 | 33333 | 4 |
| w1-invoices | PASS | 5 | 38 | 19764 | 4 |
| w1-plans-rating | PASS | 8 | 40 | 993 | 5 |
| w1-dunning | PASS | 3 | 11 | 2 | 4 |

54,534 checks, 0 failures. Log: `~/e2e/logs/wave.log` (not committed).

## Byte-identical rerun

`result.json`, `<unit>.recon.json`, `report.md` and `recon.summary.md` for all four units are
identical to the merged evidence once the `generated_at` / `Generated:` timestamp lines are
removed. One deviation found and fixed in place: the harness rewrites `recon.summary.md`
on every run, which dropped the footer line `live recon: not run, no source access` that
the invoices summary had carried by hand. The line was restored; the canonical
`<unit>.recon.json` for all four units carries it as `live_recon` regardless.

## Probes past the gate (`probes.json`)

- 15 collections populated. `customerMasterHist`, `subscriptionsHist`, `billingAuditLog` are
  in map-1 but have zero source rows in this Oracle, so no collection is created.
- No duplicate `_id` in `invoices` or `customerMaster`.
- `invoiceLine` still holds 37 lines whose `invoiceId` has no `invoiceHeader`: the finance
  feed orphans are preserved, not dropped, which is why INVOICE_HEADER/INVOICE_LINE stay
  referenced while application `invoices.lines` embeds.
- Cross-unit references: 0 subscriptions without a plan, 0 dunning attempts without an
  invoice.
- Attribute pattern: 7,075 of 25,000 customer documents carry `attributes` from
  ENTITY_ATTR_VALUE (8,333 source rows).
- Embedded application lines: 2 lines across 3 invoices, matching source child rows; the
  app-level parity queries (tier 4) were replayed by the harness, not copied from the unit
  summaries.

## Skipped

Parallel-run comparison (playbook 4 part 2) was skipped: there is no live source to compare
against in offline mode. The green streak that feeds STOP C has to come from the
customer's in-network LIVE or SNAPSHOT recon.
