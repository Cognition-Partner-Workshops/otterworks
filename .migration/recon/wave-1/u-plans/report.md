# Recon report: unit `u-plans`

- **parity PASS, merge blocked (structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed
- Mode: `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `ow-tp-map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `20261028`
- Tier 3 depth: `full`
- Generated: 2026-10-28T18:41:42.991331+00:00

## Routine parity: 3 proven, 0 unproven, 0 failed

- Cost: `{"source_statements": 66, "source_rows_fetched": 37, "target_statements": 57, "target_rows_fetched": 37, "elapsed_s": 5.163}`
- Rerun proof: fresh `pass`, evolved `unsupported` (no evolved record: pre-create the table in its previous committed shape (the prior proof's shape) and run again)

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 5 | FAIL (3 findings) |
| 1 | counts_through_mapping | 5 | PASS |
| 2 | per_field_aggregates | 32 | PASS |
| 3 | keyed_diffs | 37 | PASS |

## Tier 0 coverage
```json
{
  "plans": {
    "source": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "code"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "active_yn",
        "code",
        "id",
        "included_units",
        "monthly_fee",
        "overage_rate",
        "tier_cd"
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
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "code"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "active_yn",
        "code",
        "id",
        "included_units",
        "monthly_fee",
        "overage_rate",
        "tier_cd"
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
    "identity": null
  },
  "tenants": {
    "source": {
      "table_type": null,
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
      "table_type": null,
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
    "identity": null
  },
  "subscriptions": {
    "source": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [
        [
          [
            "plan_id"
          ],
          "ow_billing.plans",
          [
            "id"
          ],
          "no action",
          "no action"
        ],
        [
          [
            "tenant_id"
          ],
          "ow_billing.tenants",
          [
            "id"
          ],
          "no action",
          "no action"
        ]
      ],
      "foreign_keys_informational": [],
      "not_null": [
        "id",
        "plan_id",
        "starts_on",
        "status_cd",
        "tenant_id"
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
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [
        [
          [
            "plan_id"
          ],
          "mig_1793185083.plans",
          [
            "id"
          ],
          "no action",
          "no action"
        ],
        [
          [
            "tenant_id"
          ],
          "mig_1793185083.tenants",
          [
            "id"
          ],
          "no action",
          "no action"
        ]
      ],
      "foreign_keys_informational": [],
      "not_null": [
        "id",
        "plan_id",
        "starts_on",
        "status_cd",
        "tenant_id"
      ],
      "indexes": [],
      "check_count": 0,
      "checks": [],
      "identity_columns": [],
      "partial": [],
      "expression_unique": [],
      "expression_indexes": [],
      "triggers": {
        "trg_sub_no_uncancel": [
          "before",
          [
            "update"
          ],
          "row"
        ],
        "trg_subscriptions_hist": [
          "after",
          [
            "delete",
            "update"
          ],
          "row"
        ]
      },
      "grants": {},
      "unsupported": [],
      "privilege_denied": []
    },
    "identity": null
  },
  "codes": {
    "source": {
      "table_type": null,
      "primary_key": [
        "code_type",
        "code_val"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "code_desc",
        "code_type",
        "code_val"
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
      "table_type": null,
      "primary_key": [
        "code_type",
        "code_val"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "code_desc",
        "code_type",
        "code_val"
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
    "identity": null
  },
  "subscriptions_hist": {
    "source": {
      "table_type": null,
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
      "table_type": null,
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
    "identity": null
  },
  "structural_checks": {
    "constraints": "checked",
    "triggers": "checked",
    "indexes": "checked",
    "sequences_identity": "checked",
    "grants": "direct_only"
  },
  "structural_diff": {
    "subscriptions": {
      "triggers": [
        "after delete row: target 1, source 0: writes the legacy app makes today behave differently",
        "after update row: target 1, source 0: writes the legacy app makes today behave differently",
        "before update row: target 1, source 0: writes the legacy app makes today behave differently"
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
- `subscriptions` trigger_extra: after delete row: target 1, source 0: writes the legacy app makes today behave differently
- `subscriptions` trigger_extra: after update row: target 1, source 0: writes the legacy app makes today behave differently
- `subscriptions` trigger_extra: before update row: target 1, source 0: writes the legacy app makes today behave differently

## Tier 1 coverage
```json
{
  "source_counts": {
    "OW_BILLING.PLANS": 3,
    "OW_BILLING.TENANTS": 1,
    "OW_BILLING.SUBSCRIPTIONS": 1,
    "OW_BILLING.CODES": 32,
    "OW_BILLING.SUBSCRIPTIONS_HIST": 0
  }
}
```

## Tier 2 coverage
```json
{
  "deferred_to_tier3": [
    "plans.id",
    "plans.code",
    "plans.active_yn",
    "tenants.id",
    "tenants.name",
    "tenants.tax_exempt_yn",
    "subscriptions.id",
    "subscriptions.tenant_id",
    "subscriptions.plan_id",
    "codes.code_type",
    "codes.code_desc",
    "subscriptions_hist.hist_dt",
    "subscriptions_hist.hist_dt_raw",
    "subscriptions_hist.hist_op",
    "subscriptions_hist.id",
    "subscriptions_hist.tenant_id",
    "subscriptions_hist.plan_id"
  ]
}
```

## Tier 3 coverage
```json
{
  "plans": {
    "mode": "full_diff",
    "population": 3,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "tenants": {
    "mode": "full_diff",
    "population": 1,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
    "mode": "full_diff",
    "population": 1,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "codes": {
    "mode": "full_diff",
    "population": 32,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "subscriptions_hist": {
    "mode": "full_diff",
    "population": 0,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```
