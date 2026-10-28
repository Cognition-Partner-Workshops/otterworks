# Recon report: unit `u-invoice-quality-pipeline`

- **parity PASS, merge blocked (evidence, structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed; evidence: by_design_unverified
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Unverified by design: `customer_master_quarantine` unverified(by_design), `invoice_header_quarantine` unverified(by_design), `invoice_line_quarantine` unverified(by_design) (target rows <= root rows and structure graded; values not graded; merges only when the wave manifest's `by_design_unverified` declares the same objects)
- Mapping version: `ow-tp-map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `threshold`
- Generated: 2026-10-28T12:47:13.531200+00:00
- Cost: `{"source_statements": 28, "source_rows_fetched": 0, "target_statements": 28, "target_rows_fetched": 0, "elapsed_s": 14.494}`
- Rerun proof: fresh `pass`, evolved `unsupported` (evolved pre_shape equals the fresh shape: nothing evolved, so the run proves only what fresh proved)

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 3 | FAIL (3 findings) |
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 0 | PASS |

## Tier 0 coverage
```json
{
  "invoice_line_quarantine": {
    "source": {
      "table_type": null,
      "primary_key": [
        "line_id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "line_id"
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
      "table_type": "MATERIALIZED_VIEW",
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "line_id"
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
  "invoice_header_quarantine": {
    "source": {
      "table_type": null,
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
      "table_type": "MATERIALIZED_VIEW",
      "primary_key": [],
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
      "grants": {
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
  "customer_master_quarantine": {
    "source": {
      "table_type": null,
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
      "table_type": "MATERIALIZED_VIEW",
      "primary_key": [],
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
      "grants": {
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
    "invoice_line_quarantine": {
      "grants": [
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "invoice_header_quarantine": {
      "grants": [
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "customer_master_quarantine": {
      "grants": [
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    }
  },
  "platform_inherent": [],
  "dictionary": {
    "source": "live",
    "target": "live"
  }
}
```

## Tier 0 findings (3)
- `invoice_line_quarantine` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `invoice_header_quarantine` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `customer_master_quarantine` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "OW_BILLING.INVOICE_LINE": 150000,
    "OW_BILLING.INVOICE_HEADER": 18750,
    "OW_BILLING.CUSTOMER_MASTER": 25001
  },
  "by_design_unverified": [
    "invoice_line_quarantine",
    "invoice_header_quarantine",
    "customer_master_quarantine"
  ]
}
```
