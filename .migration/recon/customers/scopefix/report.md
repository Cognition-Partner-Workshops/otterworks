# Recon report: unit `customers`

- **Verdict: PASS**
- Mode: `live`
- Mapping version: `m1`
- Tolerance version: `v1`
- Seed: `20260901` | Params: `{'batch_no': '85559852'}`
- Generated: 2026-09-01T05:34:57.319769+00:00

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 40 | PASS |
| 3 | keyed_diffs | 33333 | PASS |

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "customers.sub_status_cd",
    "customers.address.line_2",
    "customers.address.line_3",
    "customers.phones.secondary.number",
    "customers.credit_limit_amt",
    "customers.legacy.promo_codes_csv",
    "customers.legacy.related_acct_ids"
  ]
}
```

## Tier 3 coverage
```json
{
  "customers": {
    "mode": "full_diff",
    "population": 25000
  },
  "embeds_graded": {
    "customers.attributes": 8333,
    "customers.history": 0
  }
}
```
