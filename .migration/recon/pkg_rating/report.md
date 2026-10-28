# Recon report: unit `pkg_rating`

- **parity PASS, merge blocked (rerun_policy, structural)**
- Verdict: FAIL (all tiers)
- Blockers: structural: structural_gap, tier_failed; rerun_policy: rerun_missing
- Mode: `transactional` (both sides live: PASS scoped to the consistency window that held and the target's applied CDC watermark)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping version: `map-v1`
- Tolerance version: `tol-20261027-v1`
- Seed: `0`
- Tier 3 depth: `threshold`
- Generated: 2026-10-28T00:53:14.411262+00:00

## Routine parity: 0 proven, 13 unproven, 0 failed

- `ow_billing.pkg_dunning.sp_schedule_dunning` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_dunning.sp_suspend_overdue` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_dunning.job_nightly_dunning` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_invoicing.compute_preview` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_invoicing.fn_invoice_preview` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_invoicing.sp_issue_invoice` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_ow_util.log_msg` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_ow_util.job_purge_audit_log` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_plans.fn_list_plans` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_plans.sp_change_plan` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.trg_subscriptions_hist` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_rating.compute_rating` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- `ow_billing.pkg_rating.sp_finalize_rating` unproven: no row in .migration/recon/pkg_rating/routine_parity.json
- Cost: `{"source_statements": 135, "source_rows_fetched": 1789, "target_statements": 123, "target_rows_fetched": 1719, "elapsed_s": 18.602}`

| Tier | Name | Checks | Result |
|---|---|---|---|
| 0 | consistency_window | 3 | PASS |
| 1 | counts_through_mapping | 3 | PASS |
| 2 | per_field_aggregates | 0 | PASS |
| 3 | keyed_diffs | 823 | PASS |
| 5 | pk_set_diff | 3 | PASS |
| 6 | cdc_lag_ordering | 0 | PASS |
| 7 | schema_parity | 3 | FAIL (1 findings) |

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
    "rating_periods": {
      "source_open": [
        "3",
        "40000000-0000-0000-0000-000000000003"
      ],
      "source_close": [
        "3",
        "40000000-0000-0000-0000-000000000003"
      ],
      "target_open": [
        3,
        "40000000-0000-0000-0000-000000000003"
      ],
      "target_close": [
        3,
        "40000000-0000-0000-0000-000000000003"
      ],
      "in_flight_at_open": 0
    },
    "rating_results": {
      "source_open": [
        "3",
        "50000000-0000-0000-0000-000000000003"
      ],
      "source_close": [
        "3",
        "50000000-0000-0000-0000-000000000003"
      ],
      "target_open": [
        3,
        "50000000-0000-0000-0000-000000000003"
      ],
      "target_close": [
        3,
        "50000000-0000-0000-0000-000000000003"
      ],
      "in_flight_at_open": 0
    },
    "usage_events": {
      "source_open": [
        "817",
        "ff743331-1aa0-1b17-064e-33db5beaeffa"
      ],
      "source_close": [
        "817",
        "ff743331-1aa0-1b17-064e-33db5beaeffa"
      ],
      "target_open": [
        817,
        "ff743331-1aa0-1b17-064e-33db5beaeffa"
      ],
      "target_close": [
        817,
        "ff743331-1aa0-1b17-064e-33db5beaeffa"
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
    "ow_billing.rating_periods": 3,
    "ow_billing.rating_results": 3,
    "ow_billing.usage_events": 817
  }
}
```

## Tier 3 coverage
```json
{
  "rating_periods": {
    "mode": "full_diff",
    "population": 3,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "rating_results": {
    "mode": "full_diff",
    "population": 3,
    "null_key_rows": {
      "source": 0,
      "target": 0
    },
    "duplicate_source_key_count": 0
  },
  "usage_events": {
    "mode": "full_diff",
    "population": 817,
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
  "rating_periods": {
    "ranges": 5,
    "population": 3,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 5,
    "keys_streamed": 14,
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
  "rating_results": {
    "ranges": 5,
    "population": 3,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 5,
    "keys_streamed": 14,
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
  "usage_events": {
    "ranges": 66,
    "population": 817,
    "fingerprint": "unavailable: every range streamed",
    "mismatched_ranges": 66,
    "keys_streamed": 1764,
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
  "rating_periods": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  },
  "rating_results": {
    "watermark": null,
    "note": "no watermark declared: the window markers alone prove stillness",
    "in_flight_deletes": 0
  },
  "usage_events": {
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
    "rating_periods: ('tenant_id',) -> ow_billing.tenants",
    "rating_periods: target FK ('tenant_id',) -> ow_tp_invoicing.tenants",
    "rating_results: ('subscription_id',) -> ow_billing.subscriptions",
    "rating_results: target FK ('subscription_id',) -> ow_tp_invoicing.subscriptions",
    "usage_events: ('tenant_id',) -> ow_billing.tenants",
    "usage_events: target FK ('tenant_id',) -> ow_tp_invoicing.tenants"
  ],
  "rating_periods": {
    "source": {
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
    "identity": null
  },
  "rating_results": {
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
            "subscription_id"
          ],
          "ow_tp_invoicing.subscriptions",
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
    "identity": null
  },
  "usage_events": {
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
      "triggers": {
        "trg_usage_events_check": [
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
    "usage_events": {
      "triggers": [
        "before insert row: target 1, source 0: writes the legacy app makes today behave differently"
      ]
    }
  },
  "dictionary": {
    "source": "live",
    "target": "live"
  }
}
```

## Tier 7 findings (1)
- `usage_events` trigger_extra: before insert row: target 1, source 0: writes the legacy app makes today behave differently
