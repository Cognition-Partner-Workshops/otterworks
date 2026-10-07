# Recon report: unit `creditNotes`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-draft-4` (sha256 `f5f8df83ed10`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `creditNotes`
- Seed: `1`
- Generated: 2026-10-07T10:39:19.747068+00:00
- 4 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
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
