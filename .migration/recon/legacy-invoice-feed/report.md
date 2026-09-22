# Recon report: unit `legacy-invoice-feed`

- **Verdict: PASS** (values redacted)
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `map-draft-3`
- Tolerance version: `tol-1`
- Seed: `1`
- Generated: 2026-09-22T21:11:06.413782+00:00
- 27 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 12 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 5 | PASS |
| 3 | keyed_diffs | 4500 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "legacyInvoiceLines": 4000,
    "legacyInvoices": 500
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "legacyInvoiceLines.invoiceNo",
    "legacyInvoiceLines.invoiceId",
    "legacyInvoiceLines.custId",
    "legacyInvoiceLines.custNo",
    "legacyInvoiceLines.custName",
    "legacyInvoiceLines.tenantId",
    "legacyInvoiceLines.lineNo",
    "legacyInvoiceLines.lineTypeCd",
    "legacyInvoiceLines.itemDesc",
    "legacyInvoiceLines.qty",
    "legacyInvoiceLines.unitPrice",
    "legacyInvoiceLines.amount",
    "legacyInvoiceLines.taxAmt",
    "legacyInvoiceLines.invoiceDt",
    "legacyInvoiceLines.servicePeriod",
    "legacyInvoiceLines.posted",
    "legacyInvoiceLines.glAcct",
    "legacyInvoiceLines.batchNo",
    "legacyInvoiceLines.srcSystem",
    "legacyInvoices.invoiceNo",
    "legacyInvoices.custId",
    "legacyInvoices.tenantId",
    "legacyInvoices.invoiceDt",
    "legacyInvoices.dueDt",
    "legacyInvoices.statusCd",
    "legacyInvoices.totalAmt",
    "legacyInvoices.batchNo"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "legacyInvoiceLines.invoiceNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.invoiceId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.custId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.custNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.custName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.itemDesc",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.servicePeriod",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoiceLines.srcSystem",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoices.invoiceNo",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoices.custId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "legacyInvoices.tenantId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    }
  ],
  "fields_fully_deferred": 22
}
```

## Tier 3 coverage
```json
{
  "legacyInvoiceLines": {
    "mode": "full_diff",
    "population": 4000,
    "duplicate_source_key_count": 0
  },
  "legacyInvoices": {
    "mode": "full_diff",
    "population": 500,
    "duplicate_source_key_count": 0
  }
}
```
