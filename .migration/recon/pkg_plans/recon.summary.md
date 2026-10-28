# Recon summary: `pkg_plans` - **parity PASS, merge blocked (rerun_policy, structural)**

- Blockers: structural: structural_gap, tier_failed; rerun_policy: rerun_missing
- Verdict: FAIL / mode `transactional` (both sides live: PASS scoped to the consistency window that held and the target's applied CDC watermark)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `threshold`
- Generated: 2026-10-28T00:53:12.768102+00:00
- Cost: source 127 statements / 282 rows fetched; target 117 statements / 215 rows; 16.982s

## Routine parity: 0 proven, 13 unproven, 0 failed

- `ow_billing.pkg_dunning.sp_schedule_dunning` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_dunning.sp_suspend_overdue` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_dunning.job_nightly_dunning` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_invoicing.compute_preview` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_invoicing.fn_invoice_preview` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_invoicing.sp_issue_invoice` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_ow_util.log_msg` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_ow_util.job_purge_audit_log` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_plans.fn_list_plans` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_plans.sp_change_plan` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.trg_subscriptions_hist` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_rating.compute_rating` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- `ow_billing.pkg_rating.sp_finalize_rating` unproven: no row in .migration/recon/pkg_plans/routine_parity.json
- Structural checks: constraints=checked, triggers=checked, indexes=checked, sequences_identity=checked, grants=direct_only
- Consistency window: source isolation `snapshot`, target isolation `repeatable_read`, held

| Tier | Checks | Result |
|---|---|---|
| 0 consistency_window | 3 | PASS |
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 73 | PASS |
| 5 pk_set_diff | 3 | PASS |
| 6 cdc_lag_ordering | 0 | PASS |
| 7 schema_parity | 3 | FAIL (3) |

Top findings (3 of 3; full list in result.json):
- T7 `subscriptions` trigger_extra: after delete row: target 1, source 0: writes the legacy app makes today behave differently
- T7 `subscriptions` trigger_extra: after update row: target 1, source 0: writes the legacy app makes today behave differently
- T7 `subscriptions` trigger_extra: before update row: target 1, source 0: writes the legacy app makes today behave differently

Full evidence: result.json, report.md (linked from the PR, not pasted).
