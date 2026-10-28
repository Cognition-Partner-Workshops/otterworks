# Recon summary: `pkg_ow_util` - **parity PASS, merge blocked (rerun_policy)**

- Blockers: rerun_policy: rerun_missing
- Verdict: PASS / mode `transactional` (both sides live: PASS scoped to the consistency window that held and the target's applied CDC watermark)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `first_run_baseline`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `threshold`
- Generated: 2026-10-28T00:53:12.035369+00:00
- Cost: source 71 statements / 129 rows fetched; target 65 statements / 97 rows; 16.246s

## Routine parity: 0 proven, 13 unproven, 0 failed

- `ow_billing.pkg_dunning.sp_schedule_dunning` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_dunning.sp_suspend_overdue` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_dunning.job_nightly_dunning` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_invoicing.compute_preview` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_invoicing.fn_invoice_preview` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_invoicing.sp_issue_invoice` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_ow_util.log_msg` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_ow_util.job_purge_audit_log` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_plans.fn_list_plans` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_plans.sp_change_plan` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.trg_subscriptions_hist` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_rating.compute_rating` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- `ow_billing.pkg_rating.sp_finalize_rating` unproven: no row in .migration/recon/pkg_ow_util/routine_parity.json
- Structural checks: constraints=checked, triggers=checked, indexes=checked, sequences_identity=checked, grants=direct_only
- Consistency window: source isolation `snapshot`, target isolation `repeatable_read`, held

| Tier | Checks | Result |
|---|---|---|
| 0 consistency_window | 2 | PASS |
| 1 counts_through_mapping | 2 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 32 | PASS |
| 5 pk_set_diff | 2 | PASS |
| 6 cdc_lag_ordering | 0 | PASS |
| 7 schema_parity | 2 | PASS |

Full evidence: result.json, report.md (linked from the PR, not pasted).
