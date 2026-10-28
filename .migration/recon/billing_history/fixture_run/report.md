# Recon report: unit `billing_history`

- **parity PASS, merge blocked (evidence, rerun_policy, structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed; evidence: routine_parity_missing, mode; rerun_policy: rerun_missing
- Mode: `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0` | Params: `{'schema': 'OW_BILLING'}`
- Tier 3 depth: `sampled`
- Generated: 2026-10-28T01:48:36.568774+00:00

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `snapshot.customer_master` no row
- `snapshot.customer_master_hist` no row
- `snapshot.entity_attr_value` no row
- `snapshot.invoice_header` no row
- `snapshot.invoice_line` no row
- Cost: `{"source_statements": 506, "source_rows_fetched": 304342, "target_statements": 347, "target_rows_fetched": 152107, "elapsed_s": 174.683}`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 5 | FAIL (19 findings) |
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 152107 | PASS |

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
      "triggers": {
        "trg_customer_master_seq": [
          "before",
          [
            "insert"
          ],
          "row"
        ],
        "trg_customer_master_hist": [
          "after",
          [
            "update",
            "delete"
          ],
          "row"
        ]
      },
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "target": {
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
  "customer_master_hist": {
    "source": {
      "primary_key": [
        "hist_id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "hist_id"
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
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "hist_id"
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
  "entity_attr_value": {
    "source": {
      "primary_key": [
        "eav_id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "attr_name",
        "eav_id",
        "entity_id",
        "entity_type"
      ],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {
        "trg_entity_attr_value_seq": [
          "before",
          [
            "insert"
          ],
          "row"
        ]
      },
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "target": {
      "primary_key": [],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "attr_name",
        "eav_id",
        "entity_id",
        "entity_type"
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
  "invoice_header": {
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
  "invoice_line": {
    "source": {
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
        "source ('cust_id',) -> expected ('cust_id',), target ()"
      ],
      "triggers": [
        "after delete row: source 1, target 0",
        "after update row: source 1, target 0",
        "before insert row: source 1, target 0"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "customer_master_hist": {
      "constraints": [
        "source ('hist_id',) -> expected ('hist_id',), target ()"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "entity_attr_value": {
      "constraints": [
        "source ('eav_id',) -> expected ('eav_id',), target ()"
      ],
      "triggers": [
        "before insert row: source 1, target 0"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "invoice_header": {
      "constraints": [
        "source ('invoice_id',) -> expected ('invoice_id',), target ()"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "invoice_line": {
      "constraints": [
        "source ('line_id',) -> expected ('line_id',), target ()"
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

## Tier 0 findings (19)
- `customer_master` primary_key_mismatch: source ('cust_id',) -> expected ('cust_id',), target ()
- `customer_master` trigger_missing: after delete row: source 1, target 0
- `customer_master` trigger_missing: after update row: source 1, target 0
- `customer_master` trigger_missing: before insert row: source 1, target 0
- `customer_master` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `customer_master` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `customer_master_hist` primary_key_mismatch: source ('hist_id',) -> expected ('hist_id',), target ()
- `customer_master_hist` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `customer_master_hist` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `entity_attr_value` primary_key_mismatch: source ('eav_id',) -> expected ('eav_id',), target ()
- `entity_attr_value` trigger_missing: before insert row: source 1, target 0
- `entity_attr_value` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `entity_attr_value` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `invoice_header` primary_key_mismatch: source ('invoice_id',) -> expected ('invoice_id',), target ()
- `invoice_header` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `invoice_header` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `invoice_line` primary_key_mismatch: source ('line_id',) -> expected ('line_id',), target ()
- `invoice_line` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `invoice_line` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_billing.customer_master": 25001,
    "ow_billing.customer_master_hist": 0,
    "ow_billing.entity_attr_value": 8337,
    "ow_billing.invoice_header": 18750,
    "ow_billing.invoice_line": 150000
  }
}
```

## Tier 3 coverage
```json
{
  "customer_master": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 25001,
    "sampled": 25001,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "customer_master_hist": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 0,
    "population": 0,
    "sampled": 0,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "entity_attr_value": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 8337,
    "sampled": 8337,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "invoice_header": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 18750,
    "sampled": 18750,
    "coverage": 1.0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "invoice_line": {
    "mode": "stratified_sample",
    "sampling": "stratified",
    "strata": 32,
    "population": 150000,
    "sampled": 100019,
    "coverage": 0.666793,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
