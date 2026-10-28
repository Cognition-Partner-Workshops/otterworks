# Recon report: unit `custbill-feed`

- **parity PASS, merge blocked (structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `full`
- Generated: 2026-10-28T02:33:20.582787+00:00

## Routine parity: 0 proven, 3 unproven, 0 failed

- `custbill.ow_tp_custbill_feed` unproven: no committed run
- `custbill.oracle_custbill_extract` unproven: no committed run
- `custbill.sftp_ingest_poll` unproven: no committed run
- Cost: `{"source_statements": 14, "source_rows_fetched": 18750, "target_statements": 9, "target_rows_fetched": 18750, "elapsed_s": 17.525}`
- Rerun proof: fresh `pass`, evolved `pass`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 1 | FAIL (3 findings) |
| 1 | counts_through_mapping | 1 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 18750 | PASS |

## Tier 0 coverage
```json
{
  "custbill_feed": {
    "source": {
      "primary_key": [
        "invoice_id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "invoice_id"
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
        "invoice_id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "cust_no",
        "invoice_id",
        "raw_line",
        "record_tag"
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
    "custbill_feed": {
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
- `custbill_feed` primary_key_informational_only: target PK is informational, not enforced: duplicate keys would be accepted
- `custbill_feed` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `custbill_feed` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_billing.invoice_header": 18750
  }
}
```

## Tier 3 coverage
```json
{
  "custbill_feed": {
    "mode": "full_diff",
    "population": 18750,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
