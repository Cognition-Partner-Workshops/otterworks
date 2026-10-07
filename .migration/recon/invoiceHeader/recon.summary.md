# Recon summary: `invoiceHeader` - **FAIL**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `1` / seed `1`
- Generated: 2026-10-07T09:40:21.832471+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | FAIL (1) |

Top findings (1 of 1; full list in result.json):
- T1 `invoiceHeader` embed_cardinality: rows(INVOICE_LINE)=1500 vs sum(len(lines))=1463

Full evidence: result.json, report.md (linked from the PR, not pasted).
