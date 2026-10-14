# Recon summary: `plans` - **PASS**

- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Mapping `v2` / tolerances `tol-v1` / seed `1`
- Generated: 2026-10-14T22:54:14.813508+00:00
- **WARNING: LOB field plans.code: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field plans.tier: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field subscriptions.tenantId: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field subscriptions.planId: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field subscriptions.status: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field tenants.name: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**
- **WARNING: LOB field tenants.status: Tier 2 aggregates skipped (driver cannot aggregate LOBs); value-checked at Tier 3 only**

| Tier | Checks | Result |
|---|---|---|
| 1 counts_through_mapping | 12 | PASS |
| 2 per_field_aggregates | 6 | PASS |
| 3 keyed_diffs | 26 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
