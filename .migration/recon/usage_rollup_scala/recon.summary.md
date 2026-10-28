# Recon summary: `usage_rollup_scala` - **parity PASS, merge blocked (structural)**

- Blockers: structural: structural_gap, tier_failed
- Verdict: FAIL / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `full`
- Generated: 2026-10-28T02:31:36.979735+00:00
- Cost: source 10 statements / 3 rows fetched; target 9 statements / 3 rows; 6.011s

## Routine parity: 0 proven, 2 unproven, 0 failed

- `analytics.ow_tp_analytics_usage_rollup` unproven: no committed run
- `analytics.usage_rollup_run` unproven: no committed run
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only
- Rerun proof: fresh `pass`, evolved `pass`

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 1 | FAIL (3) |
| 1 counts_through_mapping | 1 | PASS |
| 2 per_field_aggregates | 0 | PASS |
| 3 keyed_diffs | 3 | PASS |

Top findings (3 of 3; full list in result.json):
- T0 `usage_rollup` grant_missing: source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2
- T0 `usage_rollup` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- T0 `usage_rollup` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
