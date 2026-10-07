# Recon report: unit `invoiceHeader`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-4` (sha256 `f5f8df83ed10`)
- Tolerance version: `1` (sha256 `1a8ebb6c4c57`)
- Collections: `invoiceHeader`
- Seed: `1`
- Generated: 2026-10-07T10:01:54.913528+00:00
- **WARNING: embed invoiceHeader.lines: scoped by a where-predicate; extra target elements not checked**
- 8 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 2 | PASS |
| 3 | keyed_diffs | 2463 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoiceHeader": 1000
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "invoiceHeader.invoiceNo",
    "invoiceHeader.custId",
    "invoiceHeader.tenantId",
    "invoiceHeader.invoiceDt",
    "invoiceHeader.dueDt",
    "invoiceHeader.statusCd",
    "invoiceHeader.totalAmt",
    "invoiceHeader.batchNo"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "invoiceHeader.invoiceNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceHeader.custId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "invoiceHeader.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 6
}
```

## Tier 3 coverage
```json
{
  "invoiceHeader": {
    "mode": "full_diff",
    "population": 1000,
    "duplicate_source_key_count": 0
  },
  "embed_extras_unchecked": [
    "invoiceHeader.lines"
  ],
  "embeds_graded": {
    "invoiceHeader.lines": 1463
  }
}
```
