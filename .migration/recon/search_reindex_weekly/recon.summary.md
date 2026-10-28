# Recon summary: `search_reindex_weekly` - **parity PASS, merge blocked (structural)**

- Blockers: structural: structural_gap, tier_failed
- Verdict: FAIL / mode `live`
- Merge eligible: no (fixture/continuous evidence never merges)
- Rerun posture: `required`
- Merge authority: `harness` (human_override needs a merge_overrides entry in the committed wave manifest naming the unit)
- Mapping `map-v1` / tolerances `tol-20261027-v1` / seed `0` / depth `full`
- Generated: 2026-10-28T04:31:47.625298+00:00
- Cost: source 30 statements / 33 rows fetched; target 27 statements / 33 rows; 20.774s

## Routine parity: 0 proven, 2 unproven, 0 failed

- `analytics.ow_tp_analytics_search_reindex` unproven: no committed run
- `analytics.search_reindex_run` unproven: no committed run
- Structural checks: constraints=checked, triggers=checked, indexes=unsupported, sequences_identity=checked, grants=direct_only
- Rerun proof: fresh `pass`, evolved `pass`

| Tier | Checks | Result |
|---|---|---|
| 0 structural_parity | 3 | FAIL (9) |
| 1 counts_through_mapping | 3 | PASS |
| 2 per_field_aggregates | 5 | PASS |
| 3 keyed_diffs | 33 | PASS |

Top findings (5 of 9; full list in result.json):
- T0 `search_index_docs` grant_missing: source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2
- T0 `search_index_docs` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart
- T0 `search_index_docs` grant_extra: target grant bc8a2ef7-7af5-41c4-a4a4-0bb0d3de444d (modify,select) has no source counterpart
- T0 `search_index_docs` grant_missing: source grant d9d1c4ec-29da-4ec7-9aa0-e932710d61e2 (all_privileges,select) has no target grant for d9d1c4ec-29da-4ec7-9aa0-e932710d61e2
- T0 `search_index_docs` grant_extra: target grant 2e90bc1d-e9a1-4703-8c48-ad28ebb1864d (all_privileges) has no source counterpart

Full evidence: result.json, report.md (linked from the PR, not pasted).
