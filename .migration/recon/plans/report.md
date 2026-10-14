# Recon report: unit `plans`

- **Verdict: PASS** (values redacted)
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping version: `v2` (sha256 `6567c33adead`)
- Tolerance version: `tol-v1` (sha256 `829cbb4d2de0`)
- Collections: `plans`, `subscriptions`, `tenants`
- Seed: `1`
- Generated: 2026-10-14T22:50:08.999839+00:00
- **WARNING: LOB field plans.code: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field plans.tier: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field subscriptions.tenantId: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field subscriptions.planId: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field subscriptions.status: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field tenants.name: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field tenants.status: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- 5 fields: Tier 2 aggregates deferred to Tier 3 (rules change the value)

| Tier | Name | Checks | Result |
|---|---|---|---|
| 1 | counts_through_mapping | 12 | PASS |
| 2 | per_field_aggregates | 6 | PASS |
| 3 | keyed_diffs | 26 | PASS |

## Tier 1 coverage
```json
{
  "source_counts": {
    "plans": 3,
    "subscriptions": 9,
    "tenants": 9
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "plans.active",
    "subscriptions.startsOn",
    "subscriptions.endsOn",
    "subscriptions.suspendedOn",
    "tenants.taxExempt"
  ],
  "lob_deferred_to_tier3": [
    "plans.code",
    "plans.tier",
    "subscriptions.tenantId",
    "subscriptions.planId",
    "subscriptions.status",
    "tenants.name",
    "tenants.status"
  ],
  "fields_fully_deferred": 2
}
```

## Tier 3 coverage
```json
{
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
    "mode": "full_diff",
    "population": 9,
    "duplicate_source_key_count": 0
  },
  "tenants": {
    "mode": "full_diff",
    "population": 9,
    "duplicate_source_key_count": 0
  },
  "embeds_graded": {
    "tenants.creditNotes": 5
  }
}
```
