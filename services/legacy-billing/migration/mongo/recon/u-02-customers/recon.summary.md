# Recon summary: `u-02-customers` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-2` / tolerances `tol-2` / seed `1`
- Generated: 2026-09-26T18:27:47.375838+00:00
- **WARNING: embed customerMaster.attributes: scoped by a where-predicate; extra target elements not checked**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 30 | PASS |
| 3 keyed_diffs | 33338 | FAIL (13) |

Top findings (5 of 13; full list in result.json):
- T3 `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:0e55541bb6dc
- T3 `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:627473c9c57e
- T3 `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:3976d0c98700
- T3 `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:7e1f1398fb17
- T3 `customerMaster` field_diff: field RELATED_ACCT_IDS->relatedAcctIds key=tuple:775399c26c56

Full evidence: result.json, report.md (linked from the PR, not pasted).
