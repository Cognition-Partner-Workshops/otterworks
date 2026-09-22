# Recon report: unit `tenancy-plans`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:00:17.961716+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 4 | FAIL (1 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "tenants": 13,
    "plans": 6,
    "subscriptions": 15,
    "subscriptionVersions": 12
  }
}
```

## Tier 1 findings (1)
- `subscriptions` root_count: rows(SUBSCRIPTIONS)=15 vs docs=14
