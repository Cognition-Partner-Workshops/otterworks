# Recon report: unit `pkg_dunning`

- **parity PASS, merge blocked (structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed
- Mode: `transactional` (both sides live: PASS scoped to the consistency window that held and the target's applied CDC watermark)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `threshold`
- Generated: 2026-10-28T00:54:49.048606+00:00

## Routine parity: 0 proven, 13 unproven, 0 failed

- `ow_billing.pkg_dunning.sp_schedule_dunning` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_dunning.sp_suspend_overdue` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_dunning.job_nightly_dunning` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_invoicing.compute_preview` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_invoicing.fn_invoice_preview` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_invoicing.sp_issue_invoice` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_ow_util.log_msg` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_ow_util.job_purge_audit_log` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_plans.fn_list_plans` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_plans.sp_change_plan` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.trg_subscriptions_hist` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_rating.compute_rating` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- `ow_billing.pkg_rating.sp_finalize_rating` unproven: no row in .migration/recon/pkg_dunning/routine_parity.json
- Cost: `{"source_statements": 216, "source_rows_fetched": 548, "target_statements": 200, "target_rows_fetched": 418, "elapsed_s": 21.501}`
- Rerun proof: fresh `pass`, evolved `unsupported` (evolved pre_shape equals the fresh shape: nothing evolved, so the run proves only what fresh proved)

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | consistency_window | 4 | PASS |
| 1 | counts_through_mapping | 4 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 142 | PASS |
| 5 | pk_set_diff | 4 | PASS |
| 6 | cdc_lag_ordering | 0 | PASS |
| 7 | schema_parity | 4 | FAIL (3 findings) |

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
    "dunning_attempts": {
      "source_open": [
        "1",
        "80000000-0000-0000-0000-000000000001"
      ],
      "source_close": [
        "1",
        "80000000-0000-0000-0000-000000000001"
      ],
      "target_open": [
        1,
        "80000000-0000-0000-0000-000000000001"
      ],
      "target_close": [
        1,
        "80000000-0000-0000-0000-000000000001"
      ],
      "in_flight_at_open": 0
    },
    "notifications": {
      "source_open": [
        "1",
        "90000000-0000-0000-0000-000000000001"
      ],
      "source_close": [
        "1",
        "90000000-0000-0000-0000-000000000001"
      ],
      "target_open": [
        1,
        "90000000-0000-0000-0000-000000000001"
      ],
      "target_close": [
        1,
        "90000000-0000-0000-0000-000000000001"
      ],
      "in_flight_at_open": 0
    },
    "tenants": {
      "source_open": [
        "70",
        "fd52ea22-b475-5783-4a84-900e36eb5289"
      ],
      "source_close": [
        "70",
        "fd52ea22-b475-5783-4a84-900e36eb5289"
      ],
      "target_open": [
        70,
        "fd52ea22-b475-5783-4a84-900e36eb5289"
      ],
      "target_close": [
        70,
        "fd52ea22-b475-5783-4a84-900e36eb5289"
      ],
      "in_flight_at_open": 0
    },
    "subscriptions": {
      "source_open": [
        "70",
        "fe6f5e18-3d44-a720-dc37-a89edff1cbf6"
      ],
      "source_close": [
        "70",
        "fe6f5e18-3d44-a720-dc37-a89edff1cbf6"
      ],
      "target_open": [
        70,
        "fe6f5e18-3d44-a720-dc37-a89edff1cbf6"
      ],
      "target_close": [
        70,
        "fe6f5e18-3d44-a720-dc37-a89edff1cbf6"
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
    "ow_billing.dunning_attempts": 1,
    "ow_billing.notifications": 1,
    "ow_billing.tenants": 70,
    "ow_billing.subscriptions": 70
  }
}
```

## Tier 3 coverage
```json
{
  "dunning_attempts": {
    "mode": "full_diff",
    "population": 1,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "notifications": {
    "mode": "full_diff",
    "population": 1,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "tenants": {
    "mode": "full_diff",
    "population": 70,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "subscriptions": {
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

## Tier 5 coverage
```json
{
  "dunning_attempts": {
    "ranges": 3,
    "population": 1,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 3,
    "keys_streamed": 6,
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
  "notifications": {
    "ranges": 3,
    "population": 1,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 3,
    "keys_streamed": 6,
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
  "tenants": {
    "ranges": 66,
    "population": 70,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 66,
    "keys_streamed": 270,
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
  "subscriptions": {
    "ranges": 66,
    "population": 70,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 66,
    "keys_streamed": 270,
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
  "dunning_attempts": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  },
  "notifications": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  },
  "tenants": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  },
  "subscriptions": {
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
    "dunning_attempts: ('invoice_id',) -> ow_billing.invoices",
    "dunning_attempts: target FK ('invoice_id',) -> ow_tp_invoicing.invoices",
    "subscriptions: ('plan_id',) -> ow_billing.plans",
    "subscriptions: target FK ('plan_id',) -> ow_tp_invoicing.plans"
  ],
  "dunning_attempts": {
    "source": {
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
          "ow_tp_invoicing.invoices",
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
    "identity": null
  },
  "notifications": {
    "source": {
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
    "identity": null
  },
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
          "ow_tp_invoicing.plans",
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
  "dictionary": {
    "source": "live",
    "target": "live"
  }
}
```

## Tier 7 findings (3)
- `subscriptions` trigger_extra: after delete row: target 1, source 0: writes the legacy app makes today behave differently
- `subscriptions` trigger_extra: after update row: target 1, source 0: writes the legacy app makes today behave differently
- `subscriptions` trigger_extra: before update row: target 1, source 0: writes the legacy app makes today behave differently
