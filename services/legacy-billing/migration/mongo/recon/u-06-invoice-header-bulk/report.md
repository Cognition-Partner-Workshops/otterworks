# Recon report: unit `u-06-invoice-header-bulk`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging) | Target: `local` (local target: NOT a merge verdict)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3.1`
- Tolerance version: `tol-2`
- Seed: `1`
- Generated: 2026-09-26T18:49:14.517093+00:00
- **WARNING: embed invoiceHeader.lines: scoped by a where-predicate; extra target elements not checked**
- 8 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 2 | PASS |
| 3 | keyed_diffs | 168713 | PASS |
| 4 | app_level_parity | 3 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "invoiceHeader": 18750
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
    "population": 18750,
    "duplicate_source_key_count": 0
  },
  "embed_extras_unchecked": [
    "invoiceHeader.lines"
  ],
  "embeds_graded": {
    "invoiceHeader.lines": 149963
  }
}
```
