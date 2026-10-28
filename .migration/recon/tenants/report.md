# Recon report: unit `tenants`

- **parity PASS, merge blocked (structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `ow-tp-map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `threshold`
- Generated: 2026-10-28T01:23:54.162035+00:00
- Cost: `{"source_statements": 14, "source_rows_fetched": 70, "target_statements": 9, "target_rows_fetched": 70, "elapsed_s": 5.298}`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 1 | FAIL (3 findings) |
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 4 | PASS |
| 3 | keyed_diffs | 70 | PASS |

## Tier 0 coverage
```json
{
  "tenants": {
    "source": {
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "name"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "id",
        "name",
        "status_cd",
        "tax_exempt_yn"
      ],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {},
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "target": {
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [
        [
          "name"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "id",
        "name",
        "status_cd",
        "tax_exempt_yn"
      ],
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
    "tenants": {
      "constraints": [
        "target PK is informational, not enforced: duplicate keys would be accepted"
      ],
      "grants": [
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
- `tenants` primary_key_informational_only: target PK is informational, not enforced: duplicate keys would be accepted
- `tenants` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `tenants` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "OW_BILLING.TENANTS": 70
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "tenants.tax_exempt_yn"
  ]
}
```

## Tier 3 coverage
```json
{
  "tenants": {
    "mode": "full_diff",
    "population": 70,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
