# Recon report: unit `dunning-ops`

- **Verdict: FAIL** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:29:26.353191+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | FAIL (1 findings) |

## Tier 1 coverage
```json
{
  "source_counts": {
    "dunningAttempts": 61,
    "notifications": 21,
    "billingAuditLog": 15
  }
}
```

## Tier 1 findings (1)
- `billingAuditLog` root_count: rows(BILLING_AUDIT_LOG)=15 vs docs=14
