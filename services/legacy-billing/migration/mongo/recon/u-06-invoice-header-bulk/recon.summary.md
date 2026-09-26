# Recon summary: `u-06-invoice-header-bulk` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-2` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-26T18:07:10.184064+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 2 | FAIL (1) |

Top findings (1 of 1; full list in result.json):
- T1 `invoiceHeader` embed_cardinality: rows(INVOICE_LINE)=150000 vs sum(len(lines))=149963

Full evidence: result.json, report.md (linked from the PR, not pasted).
