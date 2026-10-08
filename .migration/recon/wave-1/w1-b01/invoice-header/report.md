# Recon report: unit `invoice-header`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1` (sha256 `a0e184e2ade2`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `invoiceHeader`
- Seed: `0`
- Generated: 2026-10-08T12:51:07.544380+00:00
- 8 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 3 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 2 | PASS |
| 3 | keyed_diffs | 1000 | PASS |

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
  }
}
```
