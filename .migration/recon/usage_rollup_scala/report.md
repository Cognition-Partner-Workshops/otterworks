# Recon report: unit `usage_rollup_scala`

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
- Generated: 2026-10-28T03:15:14.327645+00:00

## Routine parity: 0 proven, 2 unproven, 0 failed

- `analytics.ow_tp_analytics_usage_rollup` unproven: no committed run
- `analytics.usage_rollup_run` unproven: no committed run
- Cost: `{"source_statements": 10, "source_rows_fetched": 3, "target_statements": 4, "target_rows_fetched": 3, "elapsed_s": 3.988}`
- Rerun proof: fresh `pass`, evolved `pass`
- **WARNING: UNVERIFIED structural_parity: structure unavailable: usage_rollup: usage_rollup_output: information_schema.table_privileges read failed (ServerOperationError)**

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 0 | PASS |
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 3 | PASS |

## Tier 0 coverage
```json
{
  "dictionary_unavailable": [
    "usage_rollup: usage_rollup_output: information_schema.table_privileges read failed (ServerOperationError)"
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
    "ow_tp.ow_tp_analytics_src.usage_rollup_output": 3
  }
}
```

## Tier 3 coverage
```json
{
  "usage_rollup": {
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
