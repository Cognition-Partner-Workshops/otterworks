# Recon summary: `user_activity_daily` - **parity PASS, merge blocked (evidence, rerun_policy, structural)**

- Blockers: structural: structural_gap, tier_failed; evidence: routine_parity_missing, mode; rerun_policy: rerun_missing
- Verdict: FAIL / mode `fixture` (fixture data: NOT a merge verdict, run live once before merging)
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `1` / depth `full`
- Generated: 2026-10-28T04:30:07.953787+00:00
- Cost: source 10 statements / 29 rows fetched; target 9 statements / 29 rows; 8.951s

## Routine parity: routine_parity_missing (the unit has writing routines and no parity list; run `dbx-recon routine-parity` and pass `--routine-parity`)

- `analytics.ow_tp_analytics_user_activity` no row
- `analytics.user_activity_run` no row
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 1 | FAIL (3) |
| 1 counts_through_mapping | 1 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 29 | PASS |

Top findings (3 of 3; full list in result.json):
- T0 `user_activity_report` grant_missing: source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2
- T0 `user_activity_report` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- T0 `user_activity_report` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
