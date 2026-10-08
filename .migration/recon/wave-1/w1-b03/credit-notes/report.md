# Recon report: unit `credit-notes`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v3` (sha256 `c158f8bb469d`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `creditNotes`
- Seed: `0`
- Generated: 2026-10-08T13:34:24.360970+00:00
- 4 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 3 | PASS |
| 3 | keyed_diffs | 5 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "creditNotes": 5
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "creditNotes.tenantId",
    "creditNotes.issuedOn",
    "creditNotes.amount",
    "creditNotes.remainingAmount"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "creditNotes.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 1
}
```

## Tier 3 coverage
```json
{
  "creditNotes": {
    "mode": "full_diff",
    "population": 5,
    "duplicate_source_key_count": 0
  }
}
```
