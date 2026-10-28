# Recon report: unit `customer_master`

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
- Generated: 2026-10-28T01:30:12.286900+00:00
- Cost: `{"source_statements": 14, "source_rows_fetched": 25001, "target_statements": 9, "target_rows_fetched": 25001, "elapsed_s": 186.856}`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 1 | FAIL (3 findings) |
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 155 | PASS |
| 3 | keyed_diffs | 25001 | PASS |

## Tier 0 coverage
```json
{
  "customer_master": {
    "source": {
      "primary_key": [
        "cust_id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "cust_id"
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
        "cust_id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "cust_id"
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
    "customer_master": {
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
- `customer_master` primary_key_informational_only: target PK is informational, not enforced: duplicate keys would be accepted
- `customer_master` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `customer_master` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "OW_BILLING.CUSTOMER_MASTER": 25001
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "customer_master.tax_exempt_yn",
    "customer_master.credit_hold_yn",
    "customer_master.dunning_exempt_yn",
    "customer_master.vip_yn",
    "customer_master.flag_01",
    "customer_master.flag_02",
    "customer_master.flag_03",
    "customer_master.flag_04",
    "customer_master.flag_05",
    "customer_master.flag_06",
    "customer_master.flag_07",
    "customer_master.flag_08",
    "customer_master.flag_09",
    "customer_master.flag_10",
    "customer_master.flag_11",
    "customer_master.flag_12",
    "customer_master.flag_13",
    "customer_master.flag_14",
    "customer_master.flag_15",
    "customer_master.flag_16",
    "customer_master.flag_17",
    "customer_master.flag_18",
    "customer_master.flag_19",
    "customer_master.flag_20"
  ]
}
```

## Tier 3 coverage
```json
{
  "customer_master": {
    "mode": "full_diff",
    "population": 25001,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
