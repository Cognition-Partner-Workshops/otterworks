# Recon report: unit `invoicing`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `v2` (sha256 `6567c33adead`)
- Tolerance version: `tol-v1` (sha256 `829cbb4d2de0`)
- Collections: `invoices`
- Seed: `1`
- Generated: 2026-10-15T01:14:26.817371+00:00
- 2 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 1 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 7 | PASS |
| 3 | keyed_diffs | 6 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoices": 3
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoices.issuedAt",
    "invoices.status"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "invoices.status",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ]
}
```

## Tier 3 coverage
```json
{
  "invoices": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "invoices.invoiceLines": 2,
    "invoices.dunningAttempts": 1
  }
}
```
