# Recon report: unit `analytics_daily`

- **parity PASS, merge blocked (structural)**
- Verdict: PASS (all tiers)
- Blockers: structural: structural_gap, warnings
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `full`
- Generated: 2026-10-28T04:17:30.866431+00:00

## Routine parity: 0 proven, 2 unproven, 0 failed

- `analytics.ow_tp_analytics_daily` unproven: no committed run
- `analytics.analytics_daily_run` unproven: no committed run
- Cost: `{"source_statements": 20, "source_rows_fetched": 4, "target_statements": 8, "target_rows_fetched": 4, "elapsed_s": 9.921}`
- Rerun proof: fresh `pass`, evolved `pass`
- **WARNING: UNVERIFIED structural_parity: structure unavailable: analytics_daily_summary: analytics_daily_summary: information_schema.table_privileges read failed (ServerOperationError)**
- **WARNING: UNVERIFIED structural_parity: structure unavailable: analytics_daily_report: analytics_daily_report: information_schema.table_privileges read failed (ServerOperationError)**

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 0 | PASS |
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 4 | PASS |

## Tier 0 coverage
```json
{
  "dictionary_unavailable": [
    "analytics_daily_summary: analytics_daily_summary: information_schema.table_privileges read failed (ServerOperationError)",
    "analytics_daily_report: analytics_daily_report: information_schema.table_privileges read failed (ServerOperationError)"
  ],
  "structural_checks": {
    "constraints": "unsupported",
    "triggers": "unsupported",
    "indexes": "unsupported",
    "sequences_identity": "unsupported",
    "grants": "unsupported"
  },
  "structural_diff": {},
  "dictionary": {
    "source": "live",
    "target": "live"
  },
  "hole_kinds": [
    "read"
  ]
}
```

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_tp.ow_tp_analytics_src.analytics_daily_summary": 1,
    "ow_tp.ow_tp_analytics_src.analytics_daily_report": 3
  }
}
```

## Tier 3 coverage
```json
{
  "analytics_daily_summary": {
    "mode": "full_diff",
    "population": 1,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "analytics_daily_report": {
    "mode": "full_diff",
    "population": 3,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
