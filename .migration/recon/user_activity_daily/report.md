# Recon report: unit `user_activity_daily`

- **parity PASS, merge blocked (structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `1`
- Tier 3 depth: `full`
- Generated: 2026-10-28T04:30:30.364848+00:00

## Routine parity: 0 proven, 2 unproven, 0 failed

- `analytics.ow_tp_analytics_user_activity` unproven: no committed run
- `analytics.user_activity_run` unproven: no committed run
- Cost: `{"source_statements": 10, "source_rows_fetched": 29, "target_statements": 9, "target_rows_fetched": 29, "elapsed_s": 6.608}`
- Rerun proof: fresh `pass`, evolved `pass`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 1 | FAIL (3 findings) |
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 29 | PASS |

## Tier 0 coverage
```json
{
  "user_activity_report": {
    "source": {
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {
        "d9d1c4ec-29da-4ec7-9aa0-e932710d61e2": [
          "all_privileges",
          "select"
        ]
      },
      "unsupported": [
        "indexes"
      ],
      "privilege_denied": []
    },
    "target": {
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {
        "2e90bc1d-e9a1-4703-8c48-ad28ebb1864d": [
          "all_privileges"
        ],
        "bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d": [
          "modify",
          "select"
        ]
      },
      "unsupported": [
        "indexes"
      ],
      "privilege_denied": []
    },
    "identity": null
  },
  "structural_checks": {
    "constraints": "checked",
    "triggers": "checked",
    "indexes": "unsupported",
    "sequences_identity": "checked",
    "grants": "direct_only"
  },
  "structural_diff": {
    "user_activity_report": {
      "grants": [
        "source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2",
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    }
  },
  "dictionary": {
    "source": "live",
    "target": "live"
  }
}
```

## Tier 0 findings (3)
- `user_activity_report` grant_missing: source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2
- `user_activity_report` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `user_activity_report` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_tp.ow_tp_analytics_src.user_activity_report": 29
  }
}
```

## Tier 3 coverage
```json
{
  "user_activity_report": {
    "mode": "full_diff",
    "population": 29,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
