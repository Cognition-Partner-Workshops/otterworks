# Recon summary: `legacy-invoice-feed` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-22T21:10:49.641395+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | FAIL (1) |

Top findings (1 of 1; full list in result.json):
- T1 `legacyInvoiceLines` root_count: rows(INVOICE_LINE)=4000 vs docs=3999

Full evidence: result.json, report.md (linked from the PR, not pasted).
