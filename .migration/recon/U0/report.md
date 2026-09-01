# Recon report: unit `U0`

- **Verdict: FAIL**
- Mode: `live`
- Mapping version: `v1.0`
- Tolerance version: `v1`
- Seed: `714559852` | Params: `{'batch_no': '85559852', 'source_ns': 'demo'}`
- Generated: 2026-09-01T21:26:38.025245+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 14 | PASS |
| 3 | keyed_diffs | 136 | FAIL (64 findings) |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "codes.code_type",
    "codes.code_desc",
    "tenants.id",
    "tenants.name",
    "tenants.tax_exempt_yn",
    "plans.id",
    "plans.code",
    "plans.active_yn"
  ]
}
```

## Tier 3 coverage
```json
{
  "codes": {
    "mode": "full_diff",
    "population": 32
  },
  "tenants": {
    "mode": "full_diff",
    "population": 69
  },
  "plans": {
    "mode": "full_diff",
    "population": 3
  }
}
```

## Tier 3 findings (64)
- `codes` missing_doc: key=('CUST_STATUS', 1)
- `codes` missing_doc: key=('CUST_STATUS', 2)
- `codes` missing_doc: key=('CUST_STATUS', 3)
- `codes` missing_doc: key=('CUST_STATUS', 99)
- `codes` missing_doc: key=('CUST_TYPE', 1)
- `codes` missing_doc: key=('CUST_TYPE', 2)
- `codes` missing_doc: key=('CUST_TYPE', 3)
- `codes` missing_doc: key=('DUN_STATUS', 10)
- `codes` missing_doc: key=('DUN_STATUS', 20)
- `codes` missing_doc: key=('DUN_STATUS', 30)
- `codes` missing_doc: key=('INV_STATUS', 10)
- `codes` missing_doc: key=('INV_STATUS', 20)
- `codes` missing_doc: key=('INV_STATUS', 30)
- `codes` missing_doc: key=('INV_STATUS', 40)
- `codes` missing_doc: key=('NOTIF_KIND', 1)
- `codes` missing_doc: key=('NOTIF_KIND', 2)
- `codes` missing_doc: key=('NOTIF_KIND', 3)
- `codes` missing_doc: key=('PHONE_TYPE', 1)
- `codes` missing_doc: key=('PHONE_TYPE', 2)
- `codes` missing_doc: key=('PHONE_TYPE', 3)
- `codes` missing_doc: key=('PHONE_TYPE', 4)
- `codes` missing_doc: key=('PLAN_TIER', 1)
- `codes` missing_doc: key=('PLAN_TIER', 2)
- `codes` missing_doc: key=('PLAN_TIER', 3)
- `codes` missing_doc: key=('SUB_STATUS', 10)
- `codes` missing_doc: key=('SUB_STATUS', 20)
- `codes` missing_doc: key=('SUB_STATUS', 30)
- `codes` missing_doc: key=('TENANT_STATUS', 10)
- `codes` missing_doc: key=('TENANT_STATUS', 20)
- `codes` missing_doc: key=('USAGE_KIND', 1)
- `codes` missing_doc: key=('USAGE_KIND', 2)
- `codes` missing_doc: key=('USAGE_KIND', 3)
- `codes` extra_doc: key=('CUST_STATUS:1',)
- `codes` extra_doc: key=('CUST_STATUS:2',)
- `codes` extra_doc: key=('CUST_STATUS:3',)
- `codes` extra_doc: key=('CUST_STATUS:99',)
- `codes` extra_doc: key=('CUST_TYPE:1',)
- `codes` extra_doc: key=('CUST_TYPE:2',)
- `codes` extra_doc: key=('CUST_TYPE:3',)
- `codes` extra_doc: key=('DUN_STATUS:10',)
- `codes` extra_doc: key=('DUN_STATUS:20',)
- `codes` extra_doc: key=('DUN_STATUS:30',)
- `codes` extra_doc: key=('INV_STATUS:10',)
- `codes` extra_doc: key=('INV_STATUS:20',)
- `codes` extra_doc: key=('INV_STATUS:30',)
- `codes` extra_doc: key=('INV_STATUS:40',)
- `codes` extra_doc: key=('NOTIF_KIND:1',)
- `codes` extra_doc: key=('NOTIF_KIND:2',)
- `codes` extra_doc: key=('NOTIF_KIND:3',)
- `codes` extra_doc: key=('PHONE_TYPE:1',)
- ... 14 more in result.json
