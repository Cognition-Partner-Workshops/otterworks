# Recon summary: `usage-rating` - **FAIL**

- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `map-draft-3` / tolerances `tol-1` / seed `1`
- Generated: 2026-09-22T21:25:31.371420+00:00

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 3 | FAIL (2) |

Top findings (2 of 2; full list in result.json):
- T1 `ratingPeriods` root_count: rows(RATING_PERIODS)=33 vs docs=32
- T1 `ratingPeriods` embed_cardinality: rows(RATING_RESULTS)=63 vs sum(len(results))=62

Full evidence: result.json, report.md (linked from the PR, not pasted).
