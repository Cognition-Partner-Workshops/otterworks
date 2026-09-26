# Recon report: unit `w1-b02`

- **Verdict: FAIL** (values redacted)
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-v1`
- Tolerance version: `tol-v1`
- Seed: `1`
- Generated: 2026-09-26T17:35:30.259582+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 6 | FAIL (3 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "users": 500,
    "folders": 300,
    "documents": 5000,
    "comments": 12000,
    "shares": 3000,
    "audit_events": 20000
  }
}
```

## Tier 1 findings (3)
- `users` root_count: rows(users)=500 vs docs=50
- `folders` root_count: rows(folders)=300 vs docs=30
- `audit_events` root_count: rows(audit_events)=20000 vs docs=0
