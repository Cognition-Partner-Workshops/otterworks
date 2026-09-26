# Recon report: unit `w1-b02`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v1-fixture`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:28:30.467239+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 6 | FAIL (2 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "users": 50,
    "folders": 30,
    "documents": 500,
    "comments": 1200,
    "shares": 300,
    "audit_events": 2000
  }
}
```

## Tier 1 findings (2)
- `shares` root_count: rows(fx_src_shares)=300 vs docs=0
- `audit_events` root_count: rows(fx_src_audit_events)=2000 vs docs=0
