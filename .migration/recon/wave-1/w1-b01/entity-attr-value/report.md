# Recon report: unit `entity-attr-value`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: yes (fixture/continuous evidence never merges)
- Mapping version: `map-v1` (sha256 `a0e184e2ade2`)
- Tolerance version: `tol-1` (sha256 `a23d517a8e6d`)
- Collections: `entityAttrValue`
- Seed: `0`
- Generated: 2026-10-08T12:51:04.269738+00:00
- 6 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)
- 5 string fields: min/max/distinct deferred to Tier 3

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 70 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "entityAttrValue": 70
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "entityAttrValue.entityType",
    "entityAttrValue.entityId",
    "entityAttrValue.attrName",
    "entityAttrValue.attrValue",
    "entityAttrValue.attrType",
    "entityAttrValue.createdDt"
  ],
  "string_aggregates_deferred_to_tier3": [
    {
      "field": "entityAttrValue.entityType",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.entityId",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.attrName",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.attrValue",
      "stats": [
        "min",
        "max",
        "distinct_count"
      ]
    },
    {
      "field": "entityAttrValue.attrType",
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
  "entityAttrValue": {
    "mode": "full_diff",
    "population": 70,
    "duplicate_source_key_count": 0
  }
}
```
