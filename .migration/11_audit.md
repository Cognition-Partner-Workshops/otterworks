# 11 Independent audit

Audited by a session that migrated nothing, from the evidence pack alone, read-only:
https://partner-workshops.devinenterprise.com/sessions/b743ea098b874ceb94ef8d8247127311

**Verdict: FINDINGS — five, none a data defect.** The auditor re-checked the data itself and
it holds. The gaps are in evidence and in the runbook.

## What the auditor re-checked and found clean

- All five watermark recon results: `mode: live`, `verdict: PASS`, `merge_eligible: true`,
  and the tier findings arrays genuinely empty rather than summarised as passing.
- Exactly the 13 PRD collections in Atlas, no extras, counts matching the evidence pack row
  for row.
- Anomaly budget exactly 37 / 50 / 31, recomputed read-only against Atlas.
- Idempotency proved by a real second load per unit.
- The 90-day `audit_log` TTL index and the `usage_events` validator exist as claimed.
- Rollback executable, and the point-of-no-return claim true: Oracle was never modified,
  never taken read-only, never stopped, and nothing writes to Atlas.
- Wave 1's FAIL is genuinely only an output-shape problem. All four batches are `status:
  PASS`, breaker untripped, no write-target overlap or undeclared target, all four PRs in
  `merged_prs`; the workflow forces the wave verdict to FAIL whenever verifier output fails
  validation. No unit failure is hiding behind it.

## Findings and dispositions

| # | Finding | Severity | Disposition |
|---|---|---|---|
| 1 | The wave-1 independent verifier's report is not in the branch. `wave-1.result.json` points at `recon/wave-1:.migration/recon/wave-1/report.md`, which is malformed and does not exist, so the verifier's narrative claims rest on nothing committed. | medium | Accepted as an evidence gap, not closed. The unit evidence that matters is the five watermark recon runs in `recon/watermark/`, which the auditor re-checked independently and which do not depend on the verifier. Filed as skill feedback with the verdict-shape bug. |
| 2 | Runbook verification summed `invoices.totalAmount`, a field that does not exist; the field is `totals.total`. The check would have returned nothing and looked like a pass. | medium | **Fixed.** The runbook now carries the working aggregation and its expected value, 187,618,458.58. |
| 3 | The RPT-114 comparison row has no Atlas side: the report is Oracle SQL and rewriting it is unscheduled customer work. | low | **Written into the runbook as an explicit choice at STOP C**: schedule the rewrite before the window, or drop the row and accept the count and sum checks. |
| 4 | Wave 1 is formally unclosed and its disposition was a soft-mode default, not a human sign-off. | low | True. Raised as its own yes/no line at STOP C so a human signs it or doesn't. |
| 5 | The U3 recon artifact understates its own coverage: tier-3 stats key by collection, so the second mapping entry overwrites the first and a reader sees "invoices population: 3". | low | Cosmetic reporting bug in the harness, no effect on grading. `checks_run` 168,756 = 18,750 + 149,963 + 3 + 2 + 1 + 37 and reconciles exactly against Atlas. Filed as profile feedback. |

## What the auditor could not verify

- "No source write since the watermark" needs an Oracle read, which was out of bounds for
  the audit. The runbook re-checks it as a precondition before the repoint.
- This file did not exist when the audit ran, so runbook precondition 3 was formally unmet
  at that moment. It is met now by this file.
