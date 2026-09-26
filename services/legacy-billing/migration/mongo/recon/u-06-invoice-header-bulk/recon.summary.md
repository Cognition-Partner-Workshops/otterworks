# Recon summary: `u-06-invoice-header-bulk` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `tol-2` / seed `1`
- Generated: 2026-09-26T18:39:47.145133+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | FAIL (1) |

Top findings (1 of 1; full list in result.json):
- T1 `invoiceHeader` embed_cardinality: rows(INVOICE_LINE)=149963 vs sum(len(lines))=0

Full evidence: result.json, report.md (linked from the PR, not pasted).
