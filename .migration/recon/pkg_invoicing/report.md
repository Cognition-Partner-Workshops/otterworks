# Recon report: unit `pkg_invoicing`

- **parity PASS, merge blocked (rerun_policy)**
- Verdict: PASS (all tiers)
- Blockers: rerun_policy: rerun_missing
- Mode: `transactional` (both sides live: PASS scoped to the consistency window that held and the target's applied CDC watermark)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `threshold`
- Generated: 2026-10-28T00:53:13.235795+00:00

## Routine parity: 0 proven, 13 unproven, 0 failed

- `ow_billing.pkg_dunning.sp_schedule_dunning` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_dunning.sp_suspend_overdue` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_dunning.job_nightly_dunning` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_invoicing.compute_preview` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_invoicing.fn_invoice_preview` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_invoicing.sp_issue_invoice` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_ow_util.log_msg` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_ow_util.job_purge_audit_log` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_plans.fn_list_plans` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_plans.sp_change_plan` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.trg_subscriptions_hist` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_rating.compute_rating` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- `ow_billing.pkg_rating.sp_finalize_rating` unproven: no row in .migration/recon/pkg_invoicing/routine_parity.json
- Cost: `{"source_statements": 78, "source_rows_fetched": 55, "target_statements": 66, "target_rows_fetched": 42, "elapsed_s": 17.485}`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | consistency_window | 3 | PASS |
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 13 | PASS |
| 5 | pk_set_diff | 3 | PASS |
| 6 | cdc_lag_ordering | 0 | PASS |
| 7 | schema_parity | 3 | PASS |

## Tier 0 coverage
```json
{
  "isolation": {
    "source": "snapshot",
    "target": "repeatable_read"
  },
  "strength": {
    "source": "snapshot",
    "target": "snapshot"
  },
  "markers": {
    "invoices": {
      "source_open": [
        "4",
        "60000000-0000-0000-0000-000000000009"
      ],
      "source_close": [
        "4",
        "60000000-0000-0000-0000-000000000009"
      ],
      "target_open": [
        4,
        "60000000-0000-0000-0000-000000000009"
      ],
      "target_close": [
        4,
        "60000000-0000-0000-0000-000000000009"
      ],
      "in_flight_at_open": 0
    },
    "invoice_lines": {
      "source_open": [
        "4",
        "a0000000-0000-0000-0000-00000000000a"
      ],
      "source_close": [
        "4",
        "a0000000-0000-0000-0000-00000000000a"
      ],
      "target_open": [
        4,
        "a0000000-0000-0000-0000-00000000000a"
      ],
      "target_close": [
        4,
        "a0000000-0000-0000-0000-00000000000a"
      ],
      "in_flight_at_open": 0
    },
    "credit_notes": {
      "source_open": [
        "5",
        "70000000-0000-0000-0000-000000000006"
      ],
      "source_close": [
        "5",
        "70000000-0000-0000-0000-000000000006"
      ],
      "target_open": [
        5,
        "70000000-0000-0000-0000-000000000006"
      ],
      "target_close": [
        5,
        "70000000-0000-0000-0000-000000000006"
      ],
      "in_flight_at_open": 0
    }
  }
}
```

## Tier 1 coverage
```json
{
  "source_counts": {
    "ow_billing.invoices": 4,
    "ow_billing.invoice_lines": 4,
    "ow_billing.credit_notes": 5
  }
}
```

## Tier 3 coverage
```json
{
  "invoices": {
    "mode": "full_diff",
    "population": 4,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "invoice_lines": {
    "mode": "full_diff",
    "population": 4,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "credit_notes": {
    "mode": "full_diff",
    "population": 5,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  }
}
```

## Tier 5 coverage
```json
{
  "invoices": {
    "ranges": 6,
    "population": 4,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 6,
    "keys_streamed": 18,
    "missing_on_target": 0,
    "extra_on_target": 0,
    "in_flight_missing": 0,
    "in_flight_updates": 0,
    "in_flight_deletes": 0,
    "delete_evidence": {
      "status": "absent",
      "kind": null,
      "applied_position": null,
      "horizon": [
        null,
        null
      ],
      "events": 0,
      "in_flight_deletes": 0,
      "aged_deletes": 0,
      "reinserted": 0,
      "detail": ""
    },
    "rows_ahead_on_target": 0,
    "rows_behind_on_target": 0
  },
  "invoice_lines": {
    "ranges": 6,
    "population": 4,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 6,
    "keys_streamed": 18,
    "missing_on_target": 0,
    "extra_on_target": 0,
    "in_flight_missing": 0,
    "in_flight_updates": 0,
    "in_flight_deletes": 0,
    "delete_evidence": {
      "status": "absent",
      "kind": null,
      "applied_position": null,
      "horizon": [
        null,
        null
      ],
      "events": 0,
      "in_flight_deletes": 0,
      "aged_deletes": 0,
      "reinserted": 0,
      "detail": ""
    },
    "rows_ahead_on_target": 0,
    "rows_behind_on_target": 0
  },
  "credit_notes": {
    "ranges": 7,
    "population": 5,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 7,
    "keys_streamed": 22,
    "missing_on_target": 0,
    "extra_on_target": 0,
    "in_flight_missing": 0,
    "in_flight_updates": 0,
    "in_flight_deletes": 0,
    "delete_evidence": {
      "status": "absent",
      "kind": null,
      "applied_position": null,
      "horizon": [
        null,
        null
      ],
      "events": 0,
      "in_flight_deletes": 0,
      "aged_deletes": 0,
      "reinserted": 0,
      "detail": ""
    },
    "rows_ahead_on_target": 0,
    "rows_behind_on_target": 0
  }
}
```

## Tier 6 coverage
```json
{
  "invoices": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  },
  "invoice_lines": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  },
  "credit_notes": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  }
}
```

## Tier 7 coverage
```json
{
  "foreign_keys_out_of_scope": [
    "invoices: ('period_id',) -> ow_billing.rating_periods",
    "invoices: ('tenant_id',) -> ow_billing.tenants",
    "invoices: target FK ('period_id',) -> ow_tp_invoicing.rating_periods",
    "invoices: target FK ('tenant_id',) -> ow_tp_invoicing.tenants",
    "credit_notes: ('tenant_id',) -> ow_billing.tenants",
    "credit_notes: target FK ('tenant_id',) -> ow_tp_invoicing.tenants"
  ],
  "invoices": {
    "source": {
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
          "ow_tp_invoicing.rating_periods",
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
          "ow_tp_invoicing.tenants",
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
    "identity": null
  },
  "invoice_lines": {
    "source": {
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
          "ow_tp_invoicing.invoices",
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
    "identity": null
  },
  "credit_notes": {
    "source": {
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
          "ow_tp_invoicing.tenants",
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
    "identity": null
  },
  "structural_checks": {
    "constraints": "checked",
    "triggers": "checked",
    "indexes": "checked",
    "sequences_identity": "checked",
    "grants": "direct_only"
  },
  "structural_diff": {},
  "dictionary": {
    "source": "live",
    "target": "live"
  }
}
```
