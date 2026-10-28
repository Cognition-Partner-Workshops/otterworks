# Recon report: unit `custbill-ldp`

- **parity FAIL, merge blocked (data, evidence, rerun_policy, structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed; data: tier_failed; evidence: routine_parity_missing; rerun_policy: rerun_missing
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `full`
- Generated: 2026-10-28T02:54:16.112255+00:00

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `custbill.ow_tp_custbill_ldp` no row
- `custbill.parse_custbill_fixedwidth` no row
- `custbill.finance_excel_report` no row
- Cost: `{"source_statements": 28, "source_rows_fetched": 0, "target_statements": 18, "target_rows_fetched": 0, "elapsed_s": 10.029}`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 3 | FAIL (11 findings) |
| 1 | counts_through_mapping | 3 | FAIL (2 findings) |

## Tier 0 coverage
```json
{
  "parsed_records": {
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
  "quarantine": {
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
  "finance_billing_totals": {
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
    "parsed_records": {
      "constraints": [
        "source ('invoice_id',) -> expected ('invoice_id',), target ()",
        "source NOT NULL invoice_id -> target invoice_id is nullable"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "quarantine": {
      "constraints": [
        "source ('invoice_id',) -> expected ('invoice_id',), target ()",
        "source NOT NULL invoice_id -> target invoice_id is nullable"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "finance_billing_totals": {
      "constraints": [
        "source ('invoice_id',) -> expected ('invoice_id',), target ()"
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

## Tier 0 findings (11)
- `parsed_records` primary_key_mismatch: source ('invoice_id',) -> expected ('invoice_id',), target ()
- `parsed_records` not_null_missing: source NOT NULL invoice_id -> target invoice_id is nullable
- `parsed_records` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `parsed_records` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `quarantine` primary_key_mismatch: source ('invoice_id',) -> expected ('invoice_id',), target ()
- `quarantine` not_null_missing: source NOT NULL invoice_id -> target invoice_id is nullable
- `quarantine` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `quarantine` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `finance_billing_totals` primary_key_mismatch: source ('invoice_id',) -> expected ('invoice_id',), target ()
- `finance_billing_totals` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `finance_billing_totals` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_billing.invoice_header": 18750
  }
}
```

## Tier 1 findings (2)
- `quarantine` root_count: rows(ow_billing.invoice_header)=18750 vs target rows=0
- `finance_billing_totals` root_count: rows(ow_billing.invoice_header)=18750 vs target rows=204
