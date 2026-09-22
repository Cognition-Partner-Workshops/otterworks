# Recon report: unit `usage-rating`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:25:31.371420+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | FAIL (2 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "usageEvents": 133,
    "ratingPeriods": 33
  }
}
```

## Tier 1 findings (2)
- `ratingPeriods` root_count: rows(RATING_PERIODS)=33 vs docs=32
- `ratingPeriods` embed_cardinality: rows(RATING_RESULTS)=63 vs sum(len(results))=62
