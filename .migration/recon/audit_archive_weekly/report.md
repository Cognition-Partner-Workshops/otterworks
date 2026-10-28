# Recon report: unit `audit_archive_weekly`

- **parity FAIL, merge blocked (data, structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed; data: tier_failed
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `full`
- Generated: 2026-10-28T04:30:53.277848+00:00

## Routine parity: 0 proven, 2 unproven, 0 failed

- `analytics.ow_tp_analytics_audit_archive` unproven: no committed run
- `analytics.audit_archive_run` unproven: no committed run
- Cost: `{"source_statements": 20, "source_rows_fetched": 135, "target_statements": 18, "target_rows_fetched": 135, "elapsed_s": 15.36}`
- Rerun proof: fresh `pass`, evolved `pass`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 2 | FAIL (6 findings) |
| 1 | counts_through_mapping | 2 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 27 | FAIL (8 findings) |

## Tier 0 coverage
```json
{
  "audit_archive": {
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
  "audit_archive_report": {
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
    "audit_archive": {
      "grants": [
        "source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2",
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "audit_archive_report": {
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

## Tier 0 findings (6)
- `audit_archive` grant_missing: source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2
- `audit_archive` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `audit_archive` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `audit_archive_report` grant_missing: source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2
- `audit_archive_report` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `audit_archive_report` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_tp.ow_tp_analytics_src.audit_events": 120,
    "ow_tp.ow_tp_analytics_src.compliance_report": 15
  }
}
```

## Tier 3 coverage
```json
{
  "audit_archive": {
    "mode": "full_diff",
    "population": 120,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 4
  },
  "audit_archive_report": {
    "mode": "full_diff",
    "population": 15,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```

## Tier 3 findings (8)
- `audit_archive` duplicate_source_key: key=('document.share',) seen 28 times
- `audit_archive` duplicate_source_key: key=('document.view',) seen 24 times
- `audit_archive` duplicate_source_key: key=('file.download',) seen 38 times
- `audit_archive` duplicate_source_key: key=('login',) seen 30 times
- `audit_archive` duplicate_target_key: key=('document.share',) seen 28 times
- `audit_archive` duplicate_target_key: key=('document.view',) seen 24 times
- `audit_archive` duplicate_target_key: key=('file.download',) seen 38 times
- `audit_archive` duplicate_target_key: key=('login',) seen 30 times
