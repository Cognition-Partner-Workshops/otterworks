# Recon report: unit `scaffold`

- **parity NOT_RUN, merge blocked (evidence, structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed; evidence: routine_parity_missing, mode
- Mode: `structural`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `not_applicable`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `ow-tp-scaffold-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `threshold`
- Generated: 2026-10-28T10:14:50.272635+00:00

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `scaffold_ddl` no row
- Cost: `{"source_statements": 113, "source_rows_fetched": 0, "target_statements": 99, "target_rows_fetched": 0, "elapsed_s": 60.972}`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | structural_parity | 14 | FAIL (41 findings) + 14 info |

## Tier 0 coverage
```json
{
  "ow_tp.r1793176531_recon.legacy_codes": {
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "code_type",
        "code_val"
      ],
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
  "ow_tp.r1793176531_recon.legacy_tenants": {
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
      "table_type": "MANAGED",
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
  "ow_tp.r1793176531_recon.legacy_plans": {
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
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
  "ow_tp.r1793176531_recon.legacy_subscriptions": {
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "plan_id"
          ],
          "r1793176531_recon.legacy_plans",
          [
            "id"
          ]
        ],
        [
          [
            "tenant_id"
          ],
          "r1793176531_recon.legacy_tenants",
          [
            "id"
          ]
        ]
      ],
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
  "ow_tp.r1793176531_recon.legacy_usage_events": {
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
        "kind_cd",
        "occurred_at",
        "tenant_id",
        "units"
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "tenant_id"
          ],
          "r1793176531_recon.legacy_tenants",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "id",
        "kind_cd",
        "occurred_at",
        "tenant_id",
        "units"
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
  "ow_tp.r1793176531_recon.legacy_rating_periods": {
    "source": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "tenant_id",
          "period_start"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [
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
        "period_end",
        "period_start",
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [
        [
          "tenant_id",
          "period_start"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "tenant_id"
          ],
          "r1793176531_recon.legacy_tenants",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "id",
        "period_end",
        "period_start",
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
  "ow_tp.r1793176531_recon.legacy_rating_results": {
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
            "period_id"
          ],
          "ow_billing.rating_periods",
          [
            "id"
          ],
          "no action",
          "no action"
        ],
        [
          [
            "subscription_id"
          ],
          "ow_billing.subscriptions",
          [
            "id"
          ],
          "no action",
          "no action"
        ]
      ],
      "foreign_keys_informational": [],
      "not_null": [
        "billable_units",
        "created_at",
        "id",
        "overage_amount",
        "period_id",
        "quota_units",
        "rollover_units",
        "subscription_id",
        "used_units"
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "period_id"
          ],
          "r1793176531_recon.legacy_rating_periods",
          [
            "id"
          ]
        ],
        [
          [
            "subscription_id"
          ],
          "r1793176531_recon.legacy_subscriptions",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "billable_units",
        "created_at",
        "id",
        "overage_amount",
        "period_id",
        "quota_units",
        "rollover_units",
        "subscription_id",
        "used_units"
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
  "ow_tp.r1793176531_recon.legacy_invoices": {
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
            "period_id"
          ],
          "ow_billing.rating_periods",
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
        "issued_at",
        "period_id",
        "status_cd",
        "subtotal",
        "tax",
        "tenant_id",
        "total"
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "period_id"
          ],
          "r1793176531_recon.legacy_rating_periods",
          [
            "id"
          ]
        ],
        [
          [
            "tenant_id"
          ],
          "r1793176531_recon.legacy_tenants",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "id",
        "issued_at",
        "period_id",
        "status_cd",
        "subtotal",
        "tax",
        "tenant_id",
        "total"
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
  "ow_tp.r1793176531_recon.legacy_invoice_lines": {
    "source": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "invoice_id",
          "line_no"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [
        [
          [
            "invoice_id"
          ],
          "ow_billing.invoices",
          [
            "id"
          ],
          "no action",
          "cascade"
        ]
      ],
      "foreign_keys_informational": [],
      "not_null": [
        "amount",
        "description",
        "id",
        "invoice_id",
        "line_no",
        "line_type"
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [
        [
          "invoice_id",
          "line_no"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "invoice_id"
          ],
          "r1793176531_recon.legacy_invoices",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "amount",
        "description",
        "id",
        "invoice_id",
        "line_no",
        "line_type"
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
  "ow_tp.r1793176531_recon.legacy_credit_notes": {
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
        "amount",
        "id",
        "issued_on",
        "remaining_amount",
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "tenant_id"
          ],
          "r1793176531_recon.legacy_tenants",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "amount",
        "id",
        "issued_on",
        "remaining_amount",
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
  "ow_tp.r1793176531_recon.legacy_dunning_attempts": {
    "source": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "invoice_id",
          "attempt_no"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [
        [
          [
            "invoice_id"
          ],
          "ow_billing.invoices",
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
        "attempt_no",
        "id",
        "invoice_id",
        "scheduled_for",
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [
        [
          "invoice_id",
          "attempt_no"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "invoice_id"
          ],
          "r1793176531_recon.legacy_invoices",
          [
            "id"
          ]
        ],
        [
          [
            "tenant_id"
          ],
          "r1793176531_recon.legacy_tenants",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "attempt_no",
        "id",
        "invoice_id",
        "scheduled_for",
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
  "ow_tp.r1793176531_recon.legacy_notifications": {
    "source": {
      "table_type": null,
      "primary_key": [
        "id"
      ],
      "primary_key_informational": [],
      "unique": [
        [
          "tenant_id",
          "kind_cd",
          "sent_at"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [
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
        "kind_cd",
        "sent_at",
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "id"
      ],
      "unique": [
        [
          "tenant_id",
          "kind_cd",
          "sent_at"
        ]
      ],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [
        [
          [
            "tenant_id"
          ],
          "r1793176531_recon.legacy_tenants",
          [
            "id"
          ]
        ]
      ],
      "not_null": [
        "id",
        "kind_cd",
        "sent_at",
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
  "ow_tp.r1793176531_recon.legacy_billing_audit_log": {
    "source": {
      "table_type": null,
      "primary_key": [
        "log_id"
      ],
      "primary_key_informational": [],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "log_id",
        "logged_at"
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "log_id"
      ],
      "unique": [],
      "unique_nulls_equal": [],
      "foreign_keys": [],
      "foreign_keys_informational": [],
      "not_null": [
        "log_id",
        "logged_at"
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
  "ow_tp.r1793176531_recon.legacy_subscriptions_hist": {
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
      "table_type": "MANAGED",
      "primary_key": [],
      "primary_key_informational": [
        "hist_id"
      ],
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
  "structural_checks": {
    "constraints": "checked",
    "triggers": "checked",
    "indexes": "unsupported",
    "sequences_identity": "checked",
    "grants": "direct_only"
  },
  "structural_diff": {
    "ow_tp.r1793176531_recon.legacy_codes": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_tenants": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_plans": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_subscriptions": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('plan_id',) -> ow_billing.plans('id',) expected on target as (('plan_id',), 'ow_tp.r1793176531_recon.legacy_plans', ('id',))",
        "source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_usage_events": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_rating_periods": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_rating_results": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('period_id',) -> ow_billing.rating_periods('id',) expected on target as (('period_id',), 'ow_tp.r1793176531_recon.legacy_rating_periods', ('id',))",
        "source FK ('subscription_id',) -> ow_billing.subscriptions('id',) expected on target as (('subscription_id',), 'ow_tp.r1793176531_recon.legacy_subscriptions', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_invoices": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('period_id',) -> ow_billing.rating_periods('id',) expected on target as (('period_id',), 'ow_tp.r1793176531_recon.legacy_rating_periods', ('id',))",
        "source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_invoice_lines": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('invoice_id',) -> ow_billing.invoices('id',) expected on target as (('invoice_id',), 'ow_tp.r1793176531_recon.legacy_invoices', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_credit_notes": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_dunning_attempts": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('invoice_id',) -> ow_billing.invoices('id',) expected on target as (('invoice_id',), 'ow_tp.r1793176531_recon.legacy_invoices', ('id',))",
        "source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_notifications": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys",
        "source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_billing_audit_log": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    },
    "ow_tp.r1793176531_recon.legacy_subscriptions_hist": {
      "constraints": [
        "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
      ],
      "grants": [
        "target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart",
        "target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart"
      ]
    }
  },
  "platform_inherent": [
    {
      "object": "ow_tp.r1793176531_recon.legacy_codes",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_tenants",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_plans",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_subscriptions",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_usage_events",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_rating_periods",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_rating_results",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_invoices",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_invoice_lines",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_credit_notes",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_dunning_attempts",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_notifications",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_billing_audit_log",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    },
    {
      "object": "ow_tp.r1793176531_recon.legacy_subscriptions_hist",
      "check": "primary_key_informational_only",
      "detail": "target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys"
    }
  ],
  "dictionary": {
    "source": "live",
    "target": "live"
  }
}
```

## Tier 0 findings (55)
- `ow_tp.r1793176531_recon.legacy_codes` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_codes` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_codes` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_tenants` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_tenants` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_tenants` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_plans` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_plans` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_plans` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_subscriptions` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_subscriptions` foreign_key_missing: source FK ('plan_id',) -> ow_billing.plans('id',) expected on target as (('plan_id',), 'ow_tp.r1793176531_recon.legacy_plans', ('id',))
- `ow_tp.r1793176531_recon.legacy_subscriptions` foreign_key_missing: source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))
- `ow_tp.r1793176531_recon.legacy_subscriptions` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_subscriptions` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_usage_events` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_usage_events` foreign_key_missing: source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))
- `ow_tp.r1793176531_recon.legacy_usage_events` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_usage_events` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_rating_periods` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_rating_periods` foreign_key_missing: source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))
- `ow_tp.r1793176531_recon.legacy_rating_periods` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_rating_periods` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_rating_results` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_rating_results` foreign_key_missing: source FK ('period_id',) -> ow_billing.rating_periods('id',) expected on target as (('period_id',), 'ow_tp.r1793176531_recon.legacy_rating_periods', ('id',))
- `ow_tp.r1793176531_recon.legacy_rating_results` foreign_key_missing: source FK ('subscription_id',) -> ow_billing.subscriptions('id',) expected on target as (('subscription_id',), 'ow_tp.r1793176531_recon.legacy_subscriptions', ('id',))
- `ow_tp.r1793176531_recon.legacy_rating_results` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_rating_results` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_invoices` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_invoices` foreign_key_missing: source FK ('period_id',) -> ow_billing.rating_periods('id',) expected on target as (('period_id',), 'ow_tp.r1793176531_recon.legacy_rating_periods', ('id',))
- `ow_tp.r1793176531_recon.legacy_invoices` foreign_key_missing: source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))
- `ow_tp.r1793176531_recon.legacy_invoices` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_invoices` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_invoice_lines` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_invoice_lines` foreign_key_missing: source FK ('invoice_id',) -> ow_billing.invoices('id',) expected on target as (('invoice_id',), 'ow_tp.r1793176531_recon.legacy_invoices', ('id',))
- `ow_tp.r1793176531_recon.legacy_invoice_lines` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_invoice_lines` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_credit_notes` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_credit_notes` foreign_key_missing: source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))
- `ow_tp.r1793176531_recon.legacy_credit_notes` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_credit_notes` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_dunning_attempts` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_dunning_attempts` foreign_key_missing: source FK ('invoice_id',) -> ow_billing.invoices('id',) expected on target as (('invoice_id',), 'ow_tp.r1793176531_recon.legacy_invoices', ('id',))
- `ow_tp.r1793176531_recon.legacy_dunning_attempts` foreign_key_missing: source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))
- `ow_tp.r1793176531_recon.legacy_dunning_attempts` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_dunning_attempts` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_notifications` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- `ow_tp.r1793176531_recon.legacy_notifications` foreign_key_missing: source FK ('tenant_id',) -> ow_billing.tenants('id',) expected on target as (('tenant_id',), 'ow_tp.r1793176531_recon.legacy_tenants', ('id',))
- `ow_tp.r1793176531_recon.legacy_notifications` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_notifications` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- `ow_tp.r1793176531_recon.legacy_billing_audit_log` primary_key_informational_only [info]: target PK is informational (Unity Catalog does not enforce it); uniqueness probe passed: 0 rows, 0 distinct keys
- ... 5 more in result.json
